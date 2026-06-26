"""Create live_performance_metrics table (V4-6).

Revision ID: 0045
Revises: 0044
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_performance_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("coin_id", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "window_days",
            sa.Integer(),
            nullable=False,
            comment="Rolling window in days (e.g. 90, 180)",
        ),
        sa.Column("n_signals", sa.Integer(), nullable=False),
        sa.Column(
            "hit_rate",
            sa.Float(),
            nullable=True,
            comment="Fraction of BUY signals with fwd_return > 0",
        ),
        sa.Column("live_sharpe", sa.Float(), nullable=True),
        sa.Column("live_calmar", sa.Float(), nullable=True),
        sa.Column(
            "vol_mae",
            sa.Float(),
            nullable=True,
            comment="Mean absolute error of vol forecast",
        ),
        sa.ForeignKeyConstraint(
            ["coin_id"],
            ["crypto_universe.coin_id"],
            name="fk_live_perf_metrics_coin_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_live_perf_metrics_coin_computed",
        "live_performance_metrics",
        ["coin_id", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_perf_metrics_coin_computed", table_name="live_performance_metrics"
    )
    op.drop_table("live_performance_metrics")
