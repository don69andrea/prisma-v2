"""NewsRetrievalService — Query-Embedding + HNSW-Retrieval über News-Chunks."""

from backend.domain.entities.news_retrieval_result import NewsRetrievalResult
from backend.domain.repositories.news_repository import NewsRepository
from backend.infrastructure.llm.client import LLMClient

_MAX_K = 20


class NewsRetrievalService:
    def __init__(self, news_repo: NewsRepository, llm_client: LLMClient) -> None:
        self._repo = news_repo
        self._llm = llm_client

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        ticker: str | None = None,
    ) -> list[NewsRetrievalResult]:
        k = min(k, _MAX_K)
        embeddings = await self._llm.embed(
            texts=[query],
            model="voyage-3-large",
            feature="news_rag_retrieval",
        )
        if not embeddings:
            return []
        return await self._repo.find_nearest(
            query_embedding=embeddings[0],
            k=k,
            ticker=ticker,
        )
