"""create stock_daily_signals table

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_daily_signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("weighted_score", sa.Float, nullable=False),
        sa.Column("quant_score", sa.Float, nullable=False),
        sa.Column("ml_score", sa.Float, nullable=False),
        sa.Column("macro_score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("is_3a_eligible", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_stock_daily_signals_ticker_date",
        "stock_daily_signals",
        ["ticker", "snapshot_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_daily_signals_ticker_date", "stock_daily_signals")
    op.drop_table("stock_daily_signals")
