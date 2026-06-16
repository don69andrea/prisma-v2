"""add missing ml_feature columns for 19-feature model

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ml_features", sa.Column("return_6m", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("return_3m", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("vol_90d", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("price_to_52w_high", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("vol_trend", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("macd_hist", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("bb_position", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("return_1m", sa.Float(), nullable=True))
    op.add_column("ml_features", sa.Column("drawdown_12m", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("ml_features", "drawdown_12m")
    op.drop_column("ml_features", "return_1m")
    op.drop_column("ml_features", "bb_position")
    op.drop_column("ml_features", "macd_hist")
    op.drop_column("ml_features", "vol_trend")
    op.drop_column("ml_features", "price_to_52w_high")
    op.drop_column("ml_features", "vol_90d")
    op.drop_column("ml_features", "return_3m")
    op.drop_column("ml_features", "return_6m")
    op.drop_column("ml_features", "return_1m")
