# dsc26-swe-w03 · Rawaj Pay transfers that are safe to retry

DSC Summer Internship 2026 · Software Engineering track · Week 3
**Python 3.12 · FastAPI 0.141.1 · SQLAlchemy 2.0.54 · Alembic 1.19.2** · expected time 3–4 hours

## Scenario

Rawaj's mobile wallet is adding person-to-person transfers. Phones retry when the network
drops, some customers will try to send money from accounts that are not theirs, and the app
team wants a firm limit on how fast one customer can fire requests. You build the transfer API,
its two new tables and the migration that creates them.

## Set up

```bash
# repository name exactly dsc26-swe-w03, public, in your own GitHub account
git init -b main
uv venv --python 3.12
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt  # pinned versions; do not change them
pytest -q                           # public tests: they fail until you build the task
alembic upgrade head                # creates ./rawaj.db from your migrations (do not commit it)
```

## Files

| File | Who | Notes |
|---|---|---|
| `app/settings.py` | DSC, **protected** | `Settings`: `database_url`, `api_tokens` (token → customer id), `rate_limit_capacity=5`, `rate_limit_refill_per_second=1.0`, `max_transfer_piastres=2_000_000`, `clock=time.monotonic` |
| `app/db.py` | DSC, **protected** | `make_engine(url)` (handles in-memory SQLite across threads), `make_session_factory(engine)` |
| `migrations/env.py`, `migrations/versions/0001_accounts.py` | DSC, **protected** | Batch mode on; 0001 creates `accounts` |
| `tests/conftest.py`, `tests/__init__.py` | DSC, **protected** | Public fixtures (`client`, `clock`, `auth`) |
| `app/models.py` | you | `Base` and `Account` are provided; do not change them. Add `Transfer` and `IdempotencyRecord` |
| `migrations/versions/0002_*.py` | you | Creates your two tables |
| `app/main.py` | you | `create_app(settings)` and everything else (more modules in `app/` are fine) |
| `alembic.ini`, `migrations/script.py.mako` | DSC | You may use them; the hidden tests do not read `alembic.ini` |
| `AI_USAGE.md` | you | Required, see the end |

The grader replaces every **protected** file with DSC's copy before running, so changes there
have no effect.

## What to build

1. **Models** in `app/models.py`:
   - `Transfer` (table `transfers`): `id` (string, primary key, starts with `trf_`),
     `from_account_id` and `to_account_id` (foreign keys to `accounts.id`), `amount_piastres`
     (integer, `CHECK amount_piastres > 0`), `memo` (string up to 140, nullable), `status`
     (string, `"completed"`).
   - `IdempotencyRecord` (table `idempotency_records`): whatever columns you need to replay a
     response, with a **unique constraint on (customer id, key)**. Store the customer id and the
     key exactly as received, each in its own column.
2. **Migration** `migrations/versions/0002_*.py` with `down_revision = "0001"`, creating both
   tables so that the migrated database matches your models exactly (tables, columns, types,
   nullability, indexes, unique constraints; `alembic check` or autogenerate shows you the
   difference), and a `downgrade()` that removes them and leaves `accounts` and its data intact.
3. **The API** in `app/main.py`: `create_app(settings: Settings) -> FastAPI`. It must create its
   engine with the provided `app.db.make_engine(settings.database_url)` and store it as
   `app.state.engine` (tests create tables and seed accounts through it). Read every limit from
   `settings` (the hidden tests use their own tokens, customers, accounts, clock and limits), and
   use `settings.clock` for the rate limiter, never the real time.

   | Endpoint | Success | Errors (all `application/problem+json`) |
   |---|---|---|
   | `POST /v1/transfers` | 201, the transfer JSON | 401 no or bad token (with `WWW-Authenticate: Bearer`); 400 missing `Idempotency-Key`; 404 source account not owned by caller (or not existing); 409 insufficient funds; 422 invalid body, unknown fields, amount over `settings.max_transfer_piastres`, same source and destination, unknown destination, or key reused with a different body; 429 rate limited (with `Retry-After`, integer seconds ≥ 1) |
   | `GET /v1/accounts/{account_id}` | 200, `{"id", "balance_piastres", "currency"}` | 401; 404 if not the caller's |
   | `GET /v1/transfers/{transfer_id}` | 200, the transfer JSON | 401; 404 unless the caller owns the source or destination account |

   - **Authentication** on all three endpoints: only `Authorization: Bearer <token>` with a token
     from `settings.api_tokens`. A missing header, another scheme (`Basic ...`, `Token ...`),
     `Bearer` with no token, or an unknown token is a 401 problem with `WWW-Authenticate: Bearer`.
   - Problem documents (RFC 9457) have at least `type`, `title` and `status` (equal to the HTTP status).
   - Body: `from_account_id`, `to_account_id`, `amount_piastres` (a JSON integer greater than 0
     and at most `settings.max_transfer_piastres`; `150.5`, `"150"`, `true` are 422), optional
     `memo`. Any other field is 422.
   - Transfer JSON: `id`, `from_account_id`, `to_account_id`, `amount_piastres`, `memo`,
     `status`. `GET /v1/transfers/{id}` returns the same JSON as the `POST` that created it.
   - A transfer debits and credits in one transaction. No balance ever goes below zero; spending
     exactly the whole balance is allowed. A 404, 409 or 422 changes no balance.
   - **Idempotency**, per customer and key. Same key and same body replays the original status
     code and JSON body exactly, with header `Idempotent-Replayed: true`, and changes nothing.
     This applies to 201 and to 409 outcomes: a 409 replays as 409 even if the account has
     money by then. The same key with any difference in the body (amount, destination, memo) is
     422. Validation errors (422 from the body schema) are not stored. Two customers may use the
     same key independently.
   - **Rate limit**: a token bucket per customer on `POST /v1/transfers`, capacity
     `settings.rate_limit_capacity`, refilled continuously at
     `settings.rate_limit_refill_per_second` (never above capacity), checked after
     authentication and before anything else (so a request without `Idempotency-Key` on an
     empty bucket is 429). Every authenticated POST takes a token, replays included. Other
     customers are not affected.
4. **`AI_USAGE.md`**: see below.

## Public tests

`pytest -q` runs `tests/test_public.py` (5 tests) with the fixtures in `tests/conftest.py`.
They fail on the starter and pass on a correct solution. They are necessary, not sufficient.

## How grading works

Push to `dsc26-swe-w03`, then press **Submit for grading** on DSC Hex (5 runs per task per
day). The grader clones your latest commit, overwrites the protected files, copies DSC's hidden
tests into `tests_hidden/`, removes any root `conftest.py`/`pytest.ini`, ignores pytest
settings elsewhere, and runs each hidden test with `python -m pytest` from the repository root,
network off, 60 s per test and 5 minutes in all. The hidden tests run your migrations with
Alembic against a fresh SQLite file (`script_location` = `migrations/`), and build apps with
`create_app(Settings(...))` plus `Base.metadata.create_all(app.state.engine)`. Your own tests
are not run. You see each hidden test's name, pass or fail and a short hint, never the code.

| ID | Public name | What it checks | Weight |
|---|---|---|---|
| H01 | migrations: upgrade head matches the models | Fresh SQLite, `alembic upgrade head`, both new tables exist, then `compare_metadata` against `Base.metadata` is empty | 12 |
| H02 | migrations: downgrade to 0001 keeps accounts | One head whose `down_revision` is `0001`; seed an account, downgrade to `0001` (new tables gone), upgrade again, account and balance still there | 6 |
| H03 | schema: the database refuses bad rows | Direct inserts of a zero amount and of a duplicate (customer, key) raise `IntegrityError` | 6 |
| H04 | auth: missing, malformed or unknown token is 401 | No header, `Basic ...`, `Token ...`, `Bearer` with no token, unknown token, on all three endpoints; `WWW-Authenticate` present | 6 |
| H05 | authorisation: other customers' objects are 404 | Spending from, reading, and reading transfers of someone else's account (or one that does not exist); balances unchanged | 10 |
| H06 | validation: bad bodies are 422 problems | Zero, negative, over-limit, `150.5`, `"150"`, `true`, extra field, same account, unknown destination, missing field; exactly the limit passes | 8 |
| H07 | insufficient funds is 409 and changes nothing | Exact-balance transfer passes; one piastre more is 409 | 6 |
| H08 | money is conserved under random transfers | Hypothesis: random sequences of transfers among four accounts; every status and balance equals a model ledger, none negative, total constant | 14 |
| H09 | idempotency: same key and body replays exactly | Same id, status, body and `Idempotent-Replayed: true`; one debit; also replays a 409 | 10 |
| H10 | idempotency: reused key with a different body is 422; missing key is 400 | Including a changed memo | 6 |
| H11 | idempotency: keys are scoped per customer | Two customers using the same key both succeed | 4 |
| H12 | rate limit: token bucket with Retry-After | Sixth request at the same instant (replays count) is 429 with `Retry-After ≥ 1`; other customers unaffected; after the fake clock advances, requests pass again at the refill rate, up to capacity | 8 |
| H13 | transfers are visible to both parties only | Sender and receiver can `GET` it; a third customer gets 404 | 4 |
| | | **Total** | **100** |

Anti-cheating: H08 generates hundreds of random transfer sequences and compares every balance
with a model ledger, so special-casing the public amounts fails. H01 runs your real migration
against an empty database; a migration that only works on your machine's `rawaj.db` fails. Do
not commit `rawaj.db`.

## AI_USAGE.md

AI tools are allowed. Keep the three headings `## Tools`, `## What AI got wrong` and
`## In my own words`; if the file or a heading is missing, the grader stops and gives 0 with
the reason "AI_USAGE.md missing or incomplete". Under `## In my own words`, answer without AI:
"Why does a transfer to someone else's account return 404 and not 403?" and "What would happen
to a customer if your idempotency record were written in a separate transaction after the
transfer?"

Late policy: ×1.0 within 72 hours of the session starting, ×0.6 for the following 7 days,
×0.5 after that until Thu 3 Dec 23:59. W5 reopens W2–W4 at ×1.0. Your best attempt counts.
