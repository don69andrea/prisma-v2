"""Erstellt die llm_call_log-Audit-Tabelle (Issue #19).

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §3.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_call_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        # NUMERIC(10, 6) — Decimal-präzise Kosten in USD (CLAUDE.md-Geld-Regel)
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
    )
    # Cap-Check-Query filtert nach created_at — Index ist Performance-kritisch.
    op.create_index(
        "ix_llm_call_log_created_at",
        "llm_call_log",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_call_log_created_at", table_name="llm_call_log")
    op.drop_table("llm_call_log")
