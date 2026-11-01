"""Database models for Rawaj Pay."""
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
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


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    from_account_id: Mapped[str] = mapped_column(String(32), ForeignKey("accounts.id"), nullable=False)
    to_account_id: Mapped[str] = mapped_column(String(32), ForeignKey("accounts.id"), nullable=False)
    amount_piastres: Mapped[int] = mapped_column(Integer, nullable=False)
    memo: Mapped[str | None] = mapped_column(String(140), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    __table_args__ = (CheckConstraint("amount_piastres > 0", name="ck_transfers_amount_positive"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_body: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("customer_id", "key", name="uq_idempotency_customer_key"),)
