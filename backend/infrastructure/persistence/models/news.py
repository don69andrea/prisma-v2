"""SQLAlchemy-ORM-Modelle für news_documents + news_chunks (News-RAG)."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
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


class NewsDocumentORM(Base):
    __tablename__ = "news_documents"
    __table_args__ = (UniqueConstraint("url_hash", name="uq_news_documents_url_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text(), nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    content_preview: Mapped[str | None] = mapped_column(Text(), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    tickers: Mapped[list[str] | None] = mapped_column(ARRAY(String(10)), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class NewsChunkORM(Base):
    __tablename__ = "news_chunks"
    __table_args__ = (
        UniqueConstraint("news_document_id", "chunk_idx", name="uq_news_doc_chunk_idx"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_idx: Mapped[int] = mapped_column(Integer(), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(2048), nullable=False)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB(), nullable=True
    )
