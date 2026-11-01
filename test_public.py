from tests.conftest import auth

TRANSFER = {"from_account_id": "acc_dina", "to_account_id": "acc_karim", "amount_piastres": 15_000}


def balance(client, account, token):
    return client.get(f"/v1/accounts/{account}", headers=auth(token, None)).json()["balance_piastres"]


def test_transfer_moves_money(client):
    r = client.post("/v1/transfers", json=TRANSFER, headers=auth())
    assert r.status_code == 201, r.text
    assert r.json()["id"].startswith("trf_")
    assert balance(client, "acc_dina", "tok_dina") == 85_000
    assert balance(client, "acc_karim", "tok_karim") == 65_000


def test_missing_token_is_401(client):
    r = client.post("/v1/transfers", json=TRANSFER, headers={"Idempotency-Key": "k"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"].lower().startswith("bearer")


def test_cannot_spend_from_someone_elses_account(client):
    stolen = {**TRANSFER, "from_account_id": "acc_karim", "to_account_id": "acc_dina"}
    r = client.post("/v1/transfers", json=stolen, headers=auth("tok_dina"))
    assert r.status_code == 404
    assert balance(client, "acc_karim", "tok_karim") == 50_000


def test_retry_with_same_key_does_not_pay_twice(client):
    first = client.post("/v1/transfers", json=TRANSFER, headers=auth(key="retry-me"))
    second = client.post("/v1/transfers", json=TRANSFER, headers=auth(key="retry-me"))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.headers.get("idempotent-replayed") == "true"
    assert balance(client, "acc_dina", "tok_dina") == 85_000


def test_amount_must_be_whole_piastres(client):
    r = client.post("/v1/transfers", json={**TRANSFER, "amount_piastres": 150.5}, headers=auth())
    assert r.status_code == 422
