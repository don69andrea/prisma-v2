"""NewsChunk-Entity — Embedding-Chunk eines NewsArticle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.domain.entities.embedding_chunk import EMBEDDING_DIM


@dataclass(frozen=True)
class NewsChunk:
    id: UUID
    news_document_id: UUID
    chunk_idx: int
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.embedding) != EMBEDDING_DIM:
            raise ValueError(f"embedding must be {EMBEDDING_DIM}-dim, got {len(self.embedding)}")
        if self.chunk_idx < 0:
            raise ValueError(f"chunk_idx must be non-negative, got {self.chunk_idx}")
        if not self.content:
            raise ValueError("content must be non-empty")
