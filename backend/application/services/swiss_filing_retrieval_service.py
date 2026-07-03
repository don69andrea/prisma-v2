"""Application Service: Swiss RAG Retrieval."""

from __future__ import annotations

import logging

from backend.domain.entities.swiss_filing_retrieval_result import SwissFilingRetrievalResult
from backend.domain.repositories.swiss_filing_repository import SwissFilingRepository
from backend.infrastructure.llm.client import LLMClient

_logger = logging.getLogger(__name__)

_VOYAGE_MODEL = "voyage-3-large"
_MAX_K = 20


class SwissFilingRetrievalService:
    def __init__(
        self,
        repository: SwissFilingRepository,
        llm_client: LLMClient,
    ) -> None:
        self._repo = repository
        self._llm = llm_client

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        ticker: str | None = None,
        language: str | None = None,
    ) -> list[SwissFilingRetrievalResult]:
        k = max(1, min(k, _MAX_K))
        embeddings = await self._llm.embed(
            texts=[query],
            model=_VOYAGE_MODEL,
            feature="swiss_filing_rag",
        )
        if not embeddings:
            return []
        return await self._repo.find_nearest(
            query_embedding=embeddings[0],
            k=k,
            ticker=ticker,
            language=language,
        )
