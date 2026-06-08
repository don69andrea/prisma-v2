"""Port: Swiss Filing Repository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.swiss_filing_chunk import SwissFilingChunk
from backend.domain.entities.swiss_filing_retrieval_result import SwissFilingRetrievalResult


class SwissFilingRepository(ABC):
    @abstractmethod
    async def exists_by_url_hash_and_chunk(self, url_hash: str, chunk_idx: int) -> bool:
        """True wenn (url_hash, chunk_idx) bereits in der DB existiert."""

    @abstractmethod
    async def save_chunks(self, chunks: list[SwissFilingChunk]) -> None:
        """Speichert Chunks (UPSERT — idempotent bei Re-Ingestion)."""

    @abstractmethod
    async def find_nearest(
        self,
        query_embedding: list[float],
        k: int,
        ticker: str | None = None,
        language: str | None = None,
    ) -> list[SwissFilingRetrievalResult]:
        """kNN-Suche via pgvector HNSW (halfvec-Cast)."""
