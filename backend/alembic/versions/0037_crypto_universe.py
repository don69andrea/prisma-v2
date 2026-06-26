"""crypto_universe table with Top-10 crypto seed data

Revision ID: 0037
Revises: 0022
Create Date: 2026-06-21
"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    crypto_universe_table = op.create_table(
        "crypto_universe",
        sa.Column("coin_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("added_at", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("coin_id"),
        sa.UniqueConstraint("symbol"),
    )

    today = date(2026, 6, 21)

    op.bulk_insert(
        crypto_universe_table,
        [
            {"symbol": "BTC-USD", "name": "Bitcoin", "active": True, "added_at": today},
            {"symbol": "ETH-USD", "name": "Ethereum", "active": True, "added_at": today},
            {"symbol": "SOL-USD", "name": "Solana", "active": True, "added_at": today},
            {"symbol": "BNB-USD", "name": "BNB", "active": True, "added_at": today},
            {"symbol": "XRP-USD", "name": "XRP", "active": True, "added_at": today},
            {"symbol": "ADA-USD", "name": "Cardano", "active": True, "added_at": today},
            {"symbol": "AVAX-USD", "name": "Avalanche", "active": True, "added_at": today},
            {"symbol": "DOGE-USD", "name": "Dogecoin", "active": True, "added_at": today},
            {"symbol": "LINK-USD", "name": "Chainlink", "active": True, "added_at": today},
            {"symbol": "DOT-USD", "name": "Polkadot", "active": True, "added_at": today},
        ],
    )


def downgrade() -> None:
    op.drop_table("crypto_universe")
