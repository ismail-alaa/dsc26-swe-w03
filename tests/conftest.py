import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Account, Base
from app.settings import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def client(clock):
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        api_tokens={"tok_dina": "cus_dina", "tok_karim": "cus_karim"},
        clock=clock,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as s:
        s.add_all([
            Account(id="acc_dina", owner_id="cus_dina", balance_piastres=100_000),
            Account(id="acc_karim", owner_id="cus_karim", balance_piastres=50_000),
        ])
        s.commit()
    return TestClient(app)


def auth(token: str = "tok_dina", key: str | None = "key-1") -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers
