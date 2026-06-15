"""0024 — create crypto_signals table for daily snapshots.

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_signals",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("signal", sa.String(20), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("price_chf", sa.Float, nullable=True),
        sa.Column("fear_greed_value", sa.Integer, nullable=True),
        sa.Column("rsi_14", sa.Float, nullable=True),
        sa.Column("volatility_30d_pct", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_crypto_signals_ticker_date",
        "crypto_signals",
        ["ticker", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_crypto_signals_ticker_date", table_name="crypto_signals")
    op.drop_table("crypto_signals")
