# backend/alembic/versions/0042_widen_news_source_column.py
"""Widen news_documents.source column from VARCHAR(10) to VARCHAR(20).

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-22

Required for CRYPTOPANIC source (11 chars -- exceeds current VARCHAR(10) limit).
Blocker B-04, D-07: inserts with source='CRYPTOPANIC' fail without this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "news_documents",
        "source",
        type_=sa.String(20),
        existing_type=sa.String(10),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "news_documents",
        "source",
        type_=sa.String(10),
        existing_type=sa.String(20),
        nullable=False,
    )
