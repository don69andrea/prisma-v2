# backend/alembic/versions/0018_create_alerts.py
"""create alerts table

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_signal", sa.String(10), nullable=True),
        sa.Column("baseline_price", sa.Float(), nullable=True),
    )
    op.create_index("ix_alerts_ticker_active", "alerts", ["ticker", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_alerts_ticker_active", table_name="alerts")
    op.drop_table("alerts")
