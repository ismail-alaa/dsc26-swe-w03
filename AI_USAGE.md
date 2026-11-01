## Tools

I used ChatGPT to help interpret the task requirements, draft the SQLAlchemy models, Alembic migration, FastAPI endpoints, and identify edge cases for validation, transactions, idempotency, authentication, and rate limiting. I reviewed and tested the generated implementation locally.

## What AI got wrong

An initial draft treated `Request.json()` as if it were synchronous inside a synchronous FastAPI endpoint. I caught this while reviewing request handling and changed the transfer endpoint to an async handler that awaits `request.json()`.

## In my own words

1. A transfer to someone else's account returns 404 so the API does not reveal whether that account exists or belongs to another customer. This helps prevent account enumeration.

2. If the transfer commits but the idempotency record is written later in a separate transaction, a crash between those transactions can leave the money moved without a saved retry result. The customer's retry could then create a second transfer and debit them twice.
