"""Database models. `Base` and `Account` are provided by DSC: do not change them
(migration 0001 creates `accounts` exactly like this).

Add `Transfer` (table `transfers`) and `IdempotencyRecord` (table `idempotency_records`)
below, then write migrations/versions/0002_*.py so that `alembic upgrade head` creates
exactly what these models describe.
"""
from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):  # provided by DSC (migration 0001)
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)
    balance_piastres: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    __table_args__ = (CheckConstraint("balance_piastres >= 0", name="ck_accounts_balance_non_negative"),)


# TODO: class Transfer(Base): ...           table "transfers"
# TODO: class IdempotencyRecord(Base): ...  table "idempotency_records", unique (customer id, key)
