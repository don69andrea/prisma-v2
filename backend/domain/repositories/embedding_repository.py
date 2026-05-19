"""EmbeddingRepository-Port — Persistence + Retrieval fuer RAG-Pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.domain.entities.document import Document
from backend.domain.entities.embedding_chunk import EmbeddingChunk


@dataclass(frozen=True)
class RetrievalResult:
    """Ein gefundener Chunk mit Ähnlichkeitsscore (1=identisch, 0=unverwandt)."""

    chunk_id: UUID
    document_id: UUID
    chunk_idx: int
    content: str
    similarity: float
    ticker: str
    doc_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DuplicateUrl(Exception):
    """Wird geworfen wenn ein Document mit gleicher URL bereits existiert."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Document with url={url!r} already exists")
        self.url = url


class EmbeddingRepository(ABC):
    @abstractmethod
    async def save_document(self, doc: Document) -> None:
        """Persistiert ein Document. Wirft `DuplicateUrl` bei URL-Konflikt."""

    @abstractmethod
    async def save_chunks(self, chunks: list[EmbeddingChunk]) -> None:
        """Batch-Insert von Chunks. Idempotent auf (document_id, chunk_idx) — re-runs
        ueberschreiben den existierenden Eintrag (UPSERT)."""

    @abstractmethod
    async def get_document_by_url(self, url: str) -> Document | None:
        """Liefert das Document zu einer URL, oder None wenn nicht vorhanden."""

    @abstractmethod
    async def count_chunks(self, document_id: UUID) -> int:
        """Zaehlt Chunks pro Document."""

    @abstractmethod
    async def list_documents(self, *, ticker: str | None = None) -> list[Document]:
        """Liefert alle Documents, optional gefiltert nach Ticker.
        Sortiert nach ingested_at DESC."""

    @abstractmethod
    async def find_nearest(
        self,
        query_embedding: list[float],
        k: int,
        ticker: str | None = None,
    ) -> list[RetrievalResult]:
        """Cosine-Similarity-Suche via HNSW-Index. Gibt die k aehnlichsten
        Chunks zurueck, optional auf einen Ticker eingeschraenkt.
        Sortiert absteigend nach Similarity (hoechste zuerst)."""
