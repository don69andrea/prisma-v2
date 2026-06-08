# backend/alembic/versions/0014_create_news_tables.py
"""create news_documents and news_chunks tables for News-RAG

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_documents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("tickers", sa.ARRAY(sa.String(10)), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("url_hash", name="uq_news_documents_url_hash"),
    )

    op.create_table(
        "news_chunks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("news_document_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_idx", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(2048), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["news_document_id"],
            ["news_documents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("news_document_id", "chunk_idx", name="uq_news_doc_chunk_idx"),
    )

    op.create_index(
        "ix_news_documents_source",
        "news_documents",
        ["source"],
    )
    op.create_index(
        "ix_news_chunks_news_document_id",
        "news_chunks",
        ["news_document_id"],
    )


def downgrade() -> None:
    op.drop_table("news_chunks")
    op.drop_table("news_documents")
