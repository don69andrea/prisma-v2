"""create crypto_price_history table

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-20

V3 · Kap. 2.2 / 15. OHLCV für Krypto in mehreren Auflösungen (1h/4h/1d).
1d ab 2017, 1h ab 2020. Bootstrap aus CryptoDataDownload-CSV, inkrementell
via CoinGecko.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_price_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval", sa.String(5), nullable=False),  # 1h|4h|1d
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("source", sa.String(20), nullable=False, server_default="cryptodatadownload"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_crypto_price_history_ticker_ts_interval",
        "crypto_price_history",
        ["ticker", "timestamp", "interval"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_crypto_price_history_ticker_ts_interval", "crypto_price_history")
    op.drop_table("crypto_price_history")
