# backend/alembic/versions/0023_fix_news_embedding_dim.py
"""fix news_chunks and embedding_chunks embedding dimension to 1024 (voyage-3-large)

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # voyage-3-large liefert 1024 Dimensionen, nicht 2048.
    # news_chunks: created in 0014 with vector(2048) — fix to 1024.
    op.execute("DELETE FROM news_chunks")
    op.execute(
        "ALTER TABLE news_chunks ALTER COLUMN embedding TYPE vector(1024)"
        " USING embedding::vector(1024)"
    )

    # embedding_chunks (SEC-Filings RAG): created in 0008 with vector(2048) — fix to 1024.
    # Drop the HNSW index first (references the old dimension), then alter, then recreate.
    op.execute("DROP INDEX IF EXISTS ix_embedding_chunks_embedding")
    op.execute("DELETE FROM embedding_chunks")
    op.execute(
        "ALTER TABLE embedding_chunks ALTER COLUMN embedding TYPE vector(1024)"
        " USING embedding::vector(1024)"
    )
    op.execute(
        "CREATE INDEX ix_embedding_chunks_embedding "
        "ON embedding_chunks USING hnsw "
        "((embedding::halfvec(1024)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM news_chunks")
    op.execute(
        "ALTER TABLE news_chunks ALTER COLUMN embedding TYPE vector(2048)"
        " USING embedding::vector(2048)"
    )

    op.execute("DROP INDEX IF EXISTS ix_embedding_chunks_embedding")
    op.execute("DELETE FROM embedding_chunks")
    op.execute(
        "ALTER TABLE embedding_chunks ALTER COLUMN embedding TYPE vector(2048)"
        " USING embedding::vector(2048)"
    )
    op.execute(
        "CREATE INDEX ix_embedding_chunks_embedding "
        "ON embedding_chunks USING hnsw "
        "((embedding::halfvec(2048)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
