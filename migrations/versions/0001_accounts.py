"""accounts

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=False),
        sa.Column("balance_piastres", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.CheckConstraint("balance_piastres >= 0", name="ck_accounts_balance_non_negative"),
    )
    op.create_index("ix_accounts_owner_id", "accounts", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_accounts_owner_id", table_name="accounts")
    op.drop_table("accounts")
