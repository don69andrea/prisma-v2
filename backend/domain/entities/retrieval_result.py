from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RetrievalResult:
    """Ähnlichkeits-Treffer aus pgvector-HNSW-Suche."""

    chunk_id: UUID
    document_id: UUID
    chunk_idx: int
    content: str
    similarity: float  # Cosine-Ähnlichkeit, 1.0=identisch, 0.0=unverwandt
    ticker: str
    doc_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
