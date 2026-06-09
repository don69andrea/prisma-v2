"""NewsRepository-Port — Persistence + Retrieval für News-RAG-Pipeline."""

from abc import ABC, abstractmethod

from backend.domain.entities.news_article import NewsArticle
from backend.domain.entities.news_chunk import NewsChunk
from backend.domain.entities.news_retrieval_result import NewsRetrievalResult
from backend.domain.repositories.embedding_repository import DuplicateUrl


class NewsRepository(ABC):
    @abstractmethod
    async def save_article(self, article: NewsArticle) -> None:
        """Persistiert ein NewsArticle. Wirft `DuplicateUrl` bei URL-Hash-Konflikt."""

    @abstractmethod
    async def exists_by_url_hash(self, url_hash: str) -> bool:
        """Prüft ob ein Artikel mit diesem URL-Hash bereits existiert."""

    @abstractmethod
    async def save_chunks(self, chunks: list[NewsChunk]) -> None:
        """Batch-UPSERT von NewsChunks. Idempotent auf (news_document_id, chunk_idx)."""

    @abstractmethod
    async def find_nearest(
        self,
        query_embedding: list[float],
        k: int,
        ticker: str | None = None,
    ) -> list[NewsRetrievalResult]:
        """Cosine-Similarity-Suche via HNSW. Gibt k ähnlichste Chunks zurück.
        Optional auf einen Ticker eingeschränkt."""


__all__ = ["DuplicateUrl", "NewsRepository"]
