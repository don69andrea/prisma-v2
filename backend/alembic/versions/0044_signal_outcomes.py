"""Create signal_outcomes table for tracking live signal performance (V4-6).

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signal_outcomes",
        sa.Column("coin_id", sa.Integer(), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column(
            "horizon",
            sa.Integer(),
            nullable=False,
            comment="Forecast horizon in days (1 or 5)",
        ),
        sa.Column("action", sa.String(length=8), nullable=False, comment="BUY/HOLD/SELL"),
        sa.Column("size_factor", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "pred_vol",
            sa.Float(),
            nullable=True,
            comment="Predicted vol at signal time",
        ),
        sa.Column(
            "realized_fwd_return",
            sa.Float(),
            nullable=True,
            comment="Backfilled ex-post return",
        ),
        sa.Column(
            "model_version",
            sa.String(length=64),
            nullable=False,
            server_default="v1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["coin_id"],
            ["crypto_universe.coin_id"],
            name="fk_signal_outcomes_coin_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("coin_id", "signal_date", "horizon", name="pk_signal_outcomes"),
    )
    op.create_index("ix_signal_outcomes_signal_date", "signal_outcomes", ["signal_date"])
    op.create_index(
        "ix_signal_outcomes_pending",
        "signal_outcomes",
        ["realized_fwd_return"],
        postgresql_where=sa.text("realized_fwd_return IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_signal_outcomes_pending", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal_date", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
