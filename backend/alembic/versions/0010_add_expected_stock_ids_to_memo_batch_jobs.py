"""add expected_stock_ids to memo_batch_jobs

Revision ID: 0010
Revises: 0009b
Create Date: 2026-05-17

Issue #86: GET /memos/jobs/{id} returned all memos for a run, not just those
belonging to the specific batch job. expected_stock_ids stores which stocks
this batch job owns so the response can be filtered job-scoped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010"
down_revision: str | None = "0009b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memo_batch_jobs",
        sa.Column(
            "expected_stock_ids",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("memo_batch_jobs", "expected_stock_ids")
