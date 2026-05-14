"""SQLAlchemy-ORM-Modelle fuer documents + embedding_chunks (RAG Slice 1)."""

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class DocumentORM(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("url", name="uq_documents_url"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(8), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date(), nullable=False)
    url: Mapped[str] = mapped_column(Text(), nullable=False)
    raw_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EmbeddingChunkORM(Base):
    __tablename__ = "embedding_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_idx", name="uq_doc_chunk_idx"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_idx: Mapped[int] = mapped_column(Integer(), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(2048), nullable=False)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB(), nullable=True
    )
