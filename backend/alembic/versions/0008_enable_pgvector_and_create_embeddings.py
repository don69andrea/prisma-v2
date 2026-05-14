"""enable pgvector extension and create embedding tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector-Extension. Idempotent — Render-Postgres-DBs ab 2026-02-05
    # haben es als optional-Extension verfuegbar (Render-Docs).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("doc_type", sa.String(8), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("raw_text_hash", sa.String(64), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Named Constraint statt unique=True — Adapter detektiert DuplicateUrl
        # per Constraint-Name (robust gegen Postgres-Error-Message-Aenderungen)
        sa.UniqueConstraint("url", name="uq_documents_url"),
    )
    op.create_index("ix_documents_ticker", "documents", ["ticker"])

    op.create_table(
        "embedding_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_idx", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(2048), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("document_id", "chunk_idx", name="uq_doc_chunk_idx"),
    )

    # HNSW-Index mit halfvec-Cast fuer Cosine-Similarity. pgvector limitiert
    # `vector`-Typ auf 2000 dim fuer Indexierung; wir nutzen 2048 (voyage-
    # 3-large per ADR-0004). Loesung: Application-Column bleibt
    # `vector(2048)` (volle Praezision), Index nutzt `halfvec(2048)`-Cast
    # (16-bit floats, Index-Limit 4000 dim).
    #
    # Quellen:
    # - pgvector README §"Vectors" + §"HNSW":
    #   https://github.com/pgvector/pgvector#vectors
    #   https://github.com/pgvector/pgvector#hnsw
    # - `m=16` / `ef_construction=64` sind die pgvector-HNSW-Defaults
    #   (siehe README-Snippet "Index Build Options"). Sie sind fuer
    #   Korpus-Groessen ~10k-1M Vektoren etabliert; unser Slice-2-Ziel
    #   (~4000 Chunks fuer 5 Ticker) liegt am unteren Ende und braucht
    #   kein Tuning.
    # - Recall-Verlust durch halfvec ist laut pgvector-Maintainer-Hinweisen
    #   "minimal" (kein konkreter Prozentsatz im README; in pgvector-Issue
    #   #461 als "negligible for most workloads" beschrieben). Falls Slice
    #   2/3 ein Recall-Regressions-Issue zeigt, koennen wir auf
    #   `vector_cosine_ops` mit Dim<=2000 wechseln (z.B. via PCA-Reduktion
    #   oder voyage-3-small mit dim=1024) — out-of-scope fuer Slice 1.
    #
    # In Slice 1 ist die Tabelle leer; Index funktioniert trotzdem.
    op.execute(
        "CREATE INDEX ix_embedding_chunks_embedding "
        "ON embedding_chunks USING hnsw "
        "((embedding::halfvec(2048)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embedding_chunks_embedding")
    op.drop_table("embedding_chunks")
    op.drop_index("ix_documents_ticker", table_name="documents")
    op.drop_table("documents")
    # Extension wird NICHT gedroppt — andere Tabellen koennten sie zukuenftig nutzen.
