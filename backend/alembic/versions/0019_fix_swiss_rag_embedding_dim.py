# backend/alembic/versions/0019_fix_swiss_rag_embedding_dim.py
"""fix swiss_rag_chunks embedding dimension to 1024 (voyage-3-large)

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # voyage-3-large liefert 1024 Dimensionen, nicht 2048
    op.execute("DELETE FROM swiss_rag_chunks")
    op.execute("ALTER TABLE swiss_rag_chunks ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)")
    # Index neu erstellen mit korrekter Dimension
    op.execute("DROP INDEX IF EXISTS ix_swiss_rag_chunks_embedding_cosine")
    op.execute(
        "CREATE INDEX ix_swiss_rag_chunks_embedding_cosine "
        "ON swiss_rag_chunks USING hnsw "
        "((embedding::halfvec(1024)) halfvec_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM swiss_rag_chunks")
    op.execute("ALTER TABLE swiss_rag_chunks ALTER COLUMN embedding TYPE vector(2048) USING embedding::vector(2048)")
    op.execute("DROP INDEX IF EXISTS ix_swiss_rag_chunks_embedding_cosine")
    op.execute(
        "CREATE INDEX ix_swiss_rag_chunks_embedding_cosine "
        "ON swiss_rag_chunks USING hnsw "
        "((embedding::halfvec(2048)) halfvec_cosine_ops)"
    )
