"""EmbeddingChunk-Entity — ein Chunk eines Documents mit Voyage-Embedding.

Embedding-Dimension ist 1024 (voyage-3-large default output dimension).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

EMBEDDING_DIM = 1024


@dataclass(frozen=True)
class EmbeddingChunk:
    id: UUID
    document_id: UUID
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
