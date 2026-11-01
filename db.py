from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite") and (":memory:" in url or url.endswith("://")):
        # One shared in-memory database across threads (TestClient runs the app in another thread).
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
