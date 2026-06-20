"""create stock_fundamentals table

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-20

V3 · Kap. 2.2 / 15. Point-in-Time-Fundamentals. WICHTIG: `publish_date`
ist die PIT-Wahrheit (Report-Date != Publish-Date — ein Q3-Bericht wird oft
6-8 Wochen nach Quartalsende publiziert). Feature-Builder MUSS publish_date
verwenden, nie period_end (sonst Look-Ahead-Bias).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_fundamentals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("publish_date", sa.Date, nullable=True),  # PIT-Wahrheit
        sa.Column("period_type", sa.String(10), nullable=False),  # quarterly|annual
        sa.Column("pe_ratio", sa.Float, nullable=True),
        sa.Column("pb_ratio", sa.Float, nullable=True),
        sa.Column("ev_ebitda", sa.Float, nullable=True),
        sa.Column("roe", sa.Float, nullable=True),
        sa.Column("debt_equity", sa.Float, nullable=True),
        sa.Column("fcf_margin", sa.Float, nullable=True),
        sa.Column("eps_chf", sa.Float, nullable=True),
        sa.Column("eps_growth_yoy", sa.Float, nullable=True),
        sa.Column("revenue_growth", sa.Float, nullable=True),
        sa.Column("dividend_yield", sa.Float, nullable=True),
        sa.Column("dividend_growth", sa.Float, nullable=True),
        sa.Column("market_cap_chf", sa.Float, nullable=True),
        sa.Column("sector", sa.String(30), nullable=True),  # für SectorMedianService
        sa.Column("source", sa.String(20), nullable=False, server_default="eodhd"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_stock_fundamentals_ticker_period",
        "stock_fundamentals",
        ["ticker", "period_end", "period_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_fundamentals_ticker_period", "stock_fundamentals")
    op.drop_table("stock_fundamentals")
