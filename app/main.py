"""Rawaj Pay transfer API. See README.md for the endpoints, errors and rules."""
from fastapi import FastAPI

from app.db import make_engine, make_session_factory  # noqa: F401  (use these, do not edit app/db.py)
from app.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    """Return a new app.

    - Create the engine with make_engine(settings.database_url) and store it as
      app.state.engine (tests create the tables and seed accounts through it).
    - Use settings.api_tokens (token -> customer id) for authentication.
    - Use settings.clock (not time.time / time.monotonic directly) for the rate limiter.
    """
    raise NotImplementedError
