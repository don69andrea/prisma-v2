# backend/alembic/versions/0043_hitl_confirmations.py
"""Create hitl_confirmations table for HITL decision logging.

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-24

Append-only table: records human-in-the-loop proceed/abort decisions.
No FK constraint on audit_trail_id (soft ref — avoids cross-migration dependency).
UI is read-only; this table ONLY logs decisions, never triggers trading.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hitl_confirmations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "audit_trail_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("coin", sa.String(), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Index for fast lookup by audit_trail_id
    op.create_index(
        "ix_hitl_confirmations_audit_trail_id",
        "hitl_confirmations",
        ["audit_trail_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hitl_confirmations_audit_trail_id", table_name="hitl_confirmations")
    op.drop_table("hitl_confirmations")
