"""Rawaj Pay transfer API."""
from __future__ import annotations

import json
import math
import threading
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import make_engine, make_session_factory
from app.models import Account, IdempotencyRecord, Transfer
from app.settings import Settings


def _problem(status: int, title: str, detail: str | None = None, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def _transfer_json(t: Transfer) -> dict[str, Any]:
    return {
        "id": t.id,
        "from_account_id": t.from_account_id,
        "to_account_id": t.to_account_id,
        "amount_piastres": t.amount_piastres,
        "memo": t.memo,
        "status": t.status,
    }


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    engine = make_engine(settings.database_url)
    app.state.engine = engine
    sessions = make_session_factory(engine)
    app.state.session_factory = sessions

    # customer_id -> [available tokens, last refill timestamp]
    buckets: dict[str, list[float]] = {}
    bucket_lock = threading.Lock()

    def authenticate(request: Request) -> str | JSONResponse:
        value = request.headers.get("Authorization")
        if not value or not value.startswith("Bearer "):
            response = _problem(401, "Unauthorized", "A valid bearer token is required.")
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        token = value[len("Bearer "):]
        customer = settings.api_tokens.get(token) if token else None
        if customer is None:
            response = _problem(401, "Unauthorized", "A valid bearer token is required.")
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        return customer

    def take_rate_token(customer: str) -> tuple[bool, int]:
        now = float(settings.clock())
        capacity = max(0.0, float(settings.rate_limit_capacity))
        refill = float(settings.rate_limit_refill_per_second)
        with bucket_lock:
            if customer not in buckets:
                buckets[customer] = [capacity, now]
            tokens, last = buckets[customer]
            if now > last and refill > 0:
                tokens = min(capacity, tokens + (now - last) * refill)
            if tokens >= 1.0:
                buckets[customer] = [tokens - 1.0, now]
                return True, 0
            wait = math.ceil((1.0 - tokens) / refill) if refill > 0 else 1
            buckets[customer] = [tokens, now]
            return False, max(1, wait)

    @app.post("/v1/transfers")
    async def create_transfer_async(request: Request):
        customer = authenticate(request)
        if isinstance(customer, JSONResponse):
            return customer
        allowed, retry_after = take_rate_token(customer)
        if not allowed:
            response = _problem(429, "Too Many Requests", "Transfer rate limit exceeded.")
            response.headers["Retry-After"] = str(retry_after)
            return response
        key = request.headers.get("Idempotency-Key")
        if key is None or key == "":
            return _problem(400, "Bad Request", "Idempotency-Key header is required.")
        try:
            payload = await request.json()
        except Exception:
            return _problem(422, "Unprocessable Entity", "Request body must be valid JSON.")
        if not isinstance(payload, dict):
            return _problem(422, "Unprocessable Entity", "Request body must be a JSON object.")
        allowed_fields = {"from_account_id", "to_account_id", "amount_piastres", "memo"}
        if set(payload) - allowed_fields:
            return _problem(422, "Unprocessable Entity", "Unknown request fields.")
        required = {"from_account_id", "to_account_id", "amount_piastres"}
        if not required.issubset(payload):
            return _problem(422, "Unprocessable Entity", "Required fields are missing.")
        source = payload["from_account_id"]
        destination = payload["to_account_id"]
        amount = payload["amount_piastres"]
        memo = payload.get("memo")
        if not isinstance(source, str) or not isinstance(destination, str):
            return _problem(422, "Unprocessable Entity", "Account IDs must be strings.")
        if type(amount) is not int or amount <= 0 or amount > settings.max_transfer_piastres:
            return _problem(422, "Unprocessable Entity", "amount_piastres must be a positive integer within the configured limit.")
        if "memo" in payload and memo is not None and (not isinstance(memo, str) or len(memo) > 140):
            return _problem(422, "Unprocessable Entity", "memo must be a string of at most 140 characters or null.")
        if source == destination:
            return _problem(422, "Unprocessable Entity", "Source and destination accounts must differ.")

        # Preserve whether the optional memo was omitted or explicitly set to null;
        # JSON object key order itself does not affect idempotency.
        canonical_body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

        with Session(engine) as session:
            # Existing idempotency result takes precedence over current account state.
            prior = session.scalar(select(IdempotencyRecord).where(
                IdempotencyRecord.customer_id == customer,
                IdempotencyRecord.key == key,
            ))
            if prior is not None:
                if prior.request_body != canonical_body:
                    return _problem(422, "Unprocessable Entity", "Idempotency-Key was already used with a different request body.")
                replay = JSONResponse(json.loads(prior.response_body), status_code=prior.response_status,
                                      media_type="application/problem+json" if prior.response_status >= 400 else "application/json")
                replay.headers["Idempotent-Replayed"] = "true"
                return replay

            source_account = session.scalar(select(Account).where(
                Account.id == source, Account.owner_id == customer
            ))
            if source_account is None:
                return _problem(404, "Not Found", "Source account was not found.")
            destination_account = session.get(Account, destination)
            if destination_account is None:
                return _problem(422, "Unprocessable Entity", "Destination account was not found.")

            # Conditional debit prevents negative balances even if concurrent requests race.
            debit = session.execute(
                update(Account)
                .where(Account.id == source, Account.owner_id == customer, Account.balance_piastres >= amount)
                .values(balance_piastres=Account.balance_piastres - amount)
            )
            if debit.rowcount != 1:
                response_status = 409
                response_body = {"type": "about:blank", "title": "Conflict", "status": 409,
                                 "detail": "Insufficient funds."}
            else:
                session.execute(update(Account).where(Account.id == destination)
                                .values(balance_piastres=Account.balance_piastres + amount))
                transfer = Transfer(
                    id="trf_" + uuid.uuid4().hex,
                    from_account_id=source,
                    to_account_id=destination,
                    amount_piastres=amount,
                    memo=memo,
                    status="completed",
                )
                session.add(transfer)
                response_status = 201
                response_body = _transfer_json(transfer)
            record = IdempotencyRecord(
                customer_id=customer,
                key=key,
                request_body=canonical_body,
                response_status=response_status,
                response_body=json.dumps(response_body, separators=(",", ":"), ensure_ascii=False),
            )
            session.add(record)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                # A concurrent request may have won the unique-key race; replay its result.
                prior = session.scalar(select(IdempotencyRecord).where(
                    IdempotencyRecord.customer_id == customer,
                    IdempotencyRecord.key == key,
                ))
                if prior is not None and prior.request_body == canonical_body:
                    replay = JSONResponse(json.loads(prior.response_body), status_code=prior.response_status,
                                          media_type="application/problem+json" if prior.response_status >= 400 else "application/json")
                    replay.headers["Idempotent-Replayed"] = "true"
                    return replay
                return _problem(422, "Unprocessable Entity", "Idempotency-Key conflict.")
            return JSONResponse(response_body, status_code=response_status,
                                media_type="application/problem+json" if response_status >= 400 else "application/json")

    @app.get("/v1/accounts/{account_id}")
    def get_account(account_id: str, request: Request):
        customer = authenticate(request)
        if isinstance(customer, JSONResponse):
            return customer
        with Session(engine) as session:
            account = session.scalar(select(Account).where(Account.id == account_id, Account.owner_id == customer))
            if account is None:
                return _problem(404, "Not Found", "Account was not found.")
            return {"id": account.id, "balance_piastres": account.balance_piastres, "currency": account.currency}

    @app.get("/v1/transfers/{transfer_id}")
    def get_transfer(transfer_id: str, request: Request):
        customer = authenticate(request)
        if isinstance(customer, JSONResponse):
            return customer
        with Session(engine) as session:
            transfer = session.get(Transfer, transfer_id)
            if transfer is None:
                return _problem(404, "Not Found", "Transfer was not found.")
            owners = session.scalars(select(Account.owner_id).where(
                Account.id.in_([transfer.from_account_id, transfer.to_account_id])
            )).all()
            if customer not in owners:
                return _problem(404, "Not Found", "Transfer was not found.")
            return _transfer_json(transfer)

    return app
