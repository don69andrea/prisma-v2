"""create memo_batch_jobs

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-08

Hinweis: Ursprueliche Branch-Revision war "0006_memo_batch_jobs"/down="0005".
Bumped auf 0007/down="0006" wegen Migration-Kollision mit PR #64s
0006_alter_ranking_interpretation_to_1000.py (chained ebenfalls von 0005).
Neue Chain: 0005 -> 0006 (alter_ranking_interp aus PR #64)
                 -> 0007 (memo_batch_jobs aus dieser PR).
Rebase auf post-#64-Merge-main faellt damit ohne Konflikt.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memo_batch_jobs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "model_run_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("ranking_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("top_n", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "failed_stock_ids",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Constraint-Namen ohne Tabellen-Praefix: Base.metadata NAMING_CONVENTION
        # `ck_%(table_name)s_%(constraint_name)s` setzt den Praefix automatisch.
        # Explizites Praefix wuerde zu `ck_memo_batch_jobs_ck_memo_batch_jobs_*`
        # in der DB fuehren (siehe Lehre aus PR #54 build-step 5).
        sa.CheckConstraint("top_n BETWEEN 1 AND 100", name="top_n"),
        sa.CheckConstraint("language IN ('de', 'en')", name="language"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'partial', 'failed')",
            name="status",
        ),
    )
    op.create_index(
        "ix_memo_batch_jobs_model_run_id",
        "memo_batch_jobs",
        ["model_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memo_batch_jobs_model_run_id", table_name="memo_batch_jobs")
    op.drop_table("memo_batch_jobs")
