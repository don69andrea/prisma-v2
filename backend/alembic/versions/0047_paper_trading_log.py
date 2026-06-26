"""Create paper_trading_log table for V4-6b Forward Paper Log (append-only).

Revision ID: 0047
Revises: 0046
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_trading_log",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("coin", sa.String(length=32), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("size_factor", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("pred_vol", sa.Float(), nullable=True),
        sa.Column(
            "realized_fwd_return",
            sa.Float(),
            nullable=True,
            comment="Backfilled ex-post",
        ),
        sa.Column(
            "written_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_paper_trading_log_signal_date", "paper_trading_log", ["signal_date"]
    )
    op.create_index(
        "ix_paper_trading_log_coin_date",
        "paper_trading_log",
        ["coin", "signal_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_trading_log_coin_date", table_name="paper_trading_log")
    op.drop_index("ix_paper_trading_log_signal_date", table_name="paper_trading_log")
    op.drop_table("paper_trading_log")
