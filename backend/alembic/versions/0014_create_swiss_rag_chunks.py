"""Create swiss_rag_chunks table for Swiss RAG Filings.

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swiss_rag_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("chunk_idx", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(2048), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("url_hash", "chunk_idx", name="uq_swiss_rag_url_chunk"),
    )
    op.create_index("ix_swiss_rag_chunks_ticker", "swiss_rag_chunks", ["ticker"])
    op.create_index("ix_swiss_rag_chunks_url_hash", "swiss_rag_chunks", ["url_hash"])
    op.create_index("ix_swiss_rag_chunks_language", "swiss_rag_chunks", ["language"])


def downgrade() -> None:
    op.drop_index("ix_swiss_rag_chunks_language", table_name="swiss_rag_chunks")
    op.drop_index("ix_swiss_rag_chunks_url_hash", table_name="swiss_rag_chunks")
    op.drop_index("ix_swiss_rag_chunks_ticker", table_name="swiss_rag_chunks")
    op.drop_table("swiss_rag_chunks")
