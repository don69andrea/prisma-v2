"""RetrievalService — RAG-Retrieval via Voyage-Embedding + pgvector HNSW."""

from backend.domain.repositories.embedding_repository import (
    EmbeddingRepository,
    RetrievalResult,
)
from backend.infrastructure.llm.client import LLMClient

_VOYAGE_MODEL = "voyage-3-large"
_DEFAULT_K = 5
_MAX_K = 20


class RetrievalService:
    """Bettet eine Query-Text-Anfrage ein und sucht die k ähnlichsten Chunks.

    Verwendet LLMClient.embed() fuer Voyage-Embeddings, damit Cost-Tracking
    und Cap-Pruefung auch fuer Retrieval-Aufrufe greifen.
    """

    def __init__(
        self,
        embedding_repo: EmbeddingRepository,
        llm_client: LLMClient,
    ) -> None:
        self._repo = embedding_repo
        self._llm = llm_client

    async def retrieve(
        self,
        query: str,
        k: int = _DEFAULT_K,
        ticker: str | None = None,
    ) -> list[RetrievalResult]:
        """Gibt die k semantisch ähnlichsten Chunks fuer `query` zurueck.

        Args:
            query: Freitext-Suchanfrage.
            k: Anzahl Ergebnisse (max. _MAX_K).
            ticker: Optionale Einschraenkung auf einen Ticker (z.B. "AAPL").
        """
        k = min(k, _MAX_K)
        embeddings = await self._llm.embed(
            texts=[query], model=_VOYAGE_MODEL, feature="rag_retrieval"
        )
        query_embedding = embeddings[0]
        return await self._repo.find_nearest(
            query_embedding=query_embedding,
            k=k,
            ticker=ticker,
        )
