"""crypto_onchain_history table — on-chain metrics from Coin Metrics Community

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crypto_onchain_history",
        sa.Column("coin_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mvrv_z", sa.Float(), nullable=True),
        sa.Column("realized_cap", sa.Float(), nullable=True),
        sa.Column("active_addresses", sa.Float(), nullable=True),
        sa.Column("tx_volume", sa.Float(), nullable=True),
        sa.Column("exchange_netflow", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), server_default="coin_metrics", nullable=False),
        sa.ForeignKeyConstraint(
            ["coin_id"],
            ["crypto_universe.coin_id"],
        ),
        sa.PrimaryKeyConstraint("coin_id", "date"),
    )


def downgrade() -> None:
    op.drop_table("crypto_onchain_history")
