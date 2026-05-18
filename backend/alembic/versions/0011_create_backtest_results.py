"""create backtest_results table

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("top_n", sa.Integer(), nullable=False),
        sa.Column("benchmark_ticker", sa.String(20), nullable=False),
        sa.Column("prisma_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("universe_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("benchmark_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("series", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_backtest_results_model_run_id", "backtest_results", ["model_run_id"])


def downgrade() -> None:
    op.drop_index("ix_backtest_results_model_run_id", table_name="backtest_results")
    op.drop_table("backtest_results")
