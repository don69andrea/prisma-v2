"""RetrievalService — Query-Embedding + HNSW-Retrieval Orchestration."""

from backend.domain.entities.retrieval_result import RetrievalResult
from backend.domain.repositories.embedding_repository import EmbeddingRepository
from backend.infrastructure.llm.client import LLMClient

_MAX_K = 20


class RetrievalService:
    """Orchestriert Query-Embedding und Similarity-Suche."""

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
        k: int = 5,
        ticker: str | None = None,
    ) -> list[RetrievalResult]:
        """Retrieval-Pipeline: Encode Query → HNSW-Suche."""
        k = min(k, _MAX_K)
        embeddings = await self._llm.embed(
            texts=[query],
            model="voyage-3-large",
            feature="rag_retrieval",
        )
        if not embeddings:
            return []
        return await self._repo.find_nearest(
            query_embedding=embeddings[0],
            k=k,
            ticker=ticker,
        )
