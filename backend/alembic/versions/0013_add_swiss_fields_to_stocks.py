# backend/alembic/versions/0013_add_swiss_fields_to_stocks.py
"""add exchange and market_cap_chf to stocks

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("exchange", sa.String(10), nullable=True))
    op.add_column("stocks", sa.Column("market_cap_chf", sa.Numeric(18, 2), nullable=True))
    op.create_index(
        "ix_stocks_exchange",
        "stocks",
        ["exchange"],
        postgresql_where=sa.text("exchange IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_stocks_exchange", table_name="stocks")
    op.drop_column("stocks", "market_cap_chf")
    op.drop_column("stocks", "exchange")
