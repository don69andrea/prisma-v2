"""create stock_price_history table

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-20

V3 · Kap. 2.2 / 15. Roh-OHLCV für CH-Aktien. DB wird primäre Datenquelle
(yfinance nur noch Seed/Inkrement), damit Yahoo-Blockaden auf Cloud-IPs
keine Live-Requests mehr brechen.

Hinweis: PK als String(36) (app-generierte UUID) — konsistent mit 0001-0030,
nicht gen_random_uuid() wie im Spec-DDL skizziert.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_price_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CHF"),
        sa.Column("source", sa.String(20), nullable=False, server_default="yfinance"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_stock_price_history_ticker_date",
        "stock_price_history",
        ["ticker", "date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_price_history_ticker_date", "stock_price_history")
    op.drop_table("stock_price_history")
