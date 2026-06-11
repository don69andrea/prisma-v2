"""Application Service: Swiss RAG Retrieval."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.domain.entities.swiss_filing_retrieval_result import SwissFilingRetrievalResult
from backend.domain.repositories.swiss_filing_repository import SwissFilingRepository

_logger = logging.getLogger(__name__)

_VOYAGE_MODEL = "voyage-3-large"


class SwissFilingRetrievalService:
    def __init__(
        self,
        repository: SwissFilingRepository,
        voyage_client: Any,
    ) -> None:
        self._repo = repository
        self._voyage = voyage_client

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        ticker: str | None = None,
        language: str | None = None,
    ) -> list[SwissFilingRetrievalResult]:
        result = await asyncio.to_thread(self._voyage.embed, [query], model=_VOYAGE_MODEL)
        query_embedding: list[float] = result.embeddings[0]
        return await self._repo.find_nearest(
            query_embedding=query_embedding,
            k=k,
            ticker=ticker,
            language=language,
        )
