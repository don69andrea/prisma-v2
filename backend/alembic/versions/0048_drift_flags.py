"""Create drift_flags table for DriftMonitor alerts (V4-6).

Revision ID: 0048
Revises: 0047
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drift_flags",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "coin",
            sa.String(length=32),
            nullable=True,
            comment="NULL = portfolio-level flag",
        ),
        sa.Column(
            "flagged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "metric_name",
            sa.String(length=64),
            nullable=False,
            comment="live_sharpe, vol_mae, etc.",
        ),
        sa.Column("live_value", sa.Float(), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=False),
        sa.Column(
            "pct_deviation",
            sa.Float(),
            nullable=False,
            comment="(live - expected) / abs(expected)",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("alert_sent", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_drift_flags_flagged_at", "drift_flags", ["flagged_at"])
    op.create_index(
        "ix_drift_flags_active",
        "drift_flags",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_drift_flags_active", table_name="drift_flags")
    op.drop_index("ix_drift_flags_flagged_at", table_name="drift_flags")
    op.drop_table("drift_flags")
