"""Unit-Tests für SwissFilingRetrievalService."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.application.services.swiss_filing_retrieval_service import (
    SwissFilingRetrievalService,
)
from backend.domain.entities.swiss_filing_retrieval_result import SwissFilingRetrievalResult

pytestmark = pytest.mark.unit

_SAMPLE_RESULT = SwissFilingRetrievalResult(
    chunk_id=uuid4(),
    chunk_idx=0,
    url="https://example.com/annual-2023.pdf",
    ticker="NESN",
    source="IR",
    language="en",
    filing_date=date(2024, 3, 1),
    doc_type="Annual Report",
    content="Nestlé reported strong results in fiscal 2023.",
    similarity=0.89,
    metadata={},
)


def _build_service(
    retrieval_results: list[SwissFilingRetrievalResult] | None = None,
    embeddings: list[list[float]] | None = None,
) -> tuple[SwissFilingRetrievalService, MagicMock, AsyncMock]:
    mock_llm = MagicMock()
    mock_llm.embed = AsyncMock(return_value=[[0.1] * 1024] if embeddings is None else embeddings)

    mock_repo = AsyncMock()
    mock_repo.find_nearest.return_value = retrieval_results or []

    svc = SwissFilingRetrievalService(repository=mock_repo, llm_client=mock_llm)
    return svc, mock_llm, mock_repo


class TestSwissFilingRetrievalService:
    async def test_retrieve_calls_embed_and_repo(self) -> None:
        svc, mock_llm, mock_repo = _build_service([_SAMPLE_RESULT])
        results = await svc.retrieve("NESN Jahresumsatz 2023")
        mock_llm.embed.assert_called_once()
        mock_repo.find_nearest.assert_called_once()
        assert len(results) == 1

    async def test_retrieve_uses_cost_tracked_embed_feature(self) -> None:
        svc, mock_llm, _ = _build_service()
        await svc.retrieve("query")
        call_kwargs = mock_llm.embed.call_args.kwargs
        assert call_kwargs["feature"] == "swiss_filing_rag"

    async def test_retrieve_clamps_k_to_max(self) -> None:
        svc, _, mock_repo = _build_service()
        await svc.retrieve("query", k=100000)
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["k"] == 20

    async def test_retrieve_clamps_k_to_minimum(self) -> None:
        svc, _, mock_repo = _build_service()
        await svc.retrieve("query", k=0)
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["k"] == 1

    async def test_retrieve_empty_embedding_returns_empty(self) -> None:
        svc, _, mock_repo = _build_service(embeddings=[])
        results = await svc.retrieve("query")
        assert results == []
        mock_repo.find_nearest.assert_not_called()

    async def test_retrieve_passes_ticker_filter(self) -> None:
        svc, _, mock_repo = _build_service()
        await svc.retrieve("dividende", ticker="NESN")
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["ticker"] == "NESN"

    async def test_retrieve_passes_language_filter(self) -> None:
        svc, _, mock_repo = _build_service()
        await svc.retrieve("bericht", language="de")
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["language"] == "de"

    async def test_retrieve_default_k(self) -> None:
        svc, _, mock_repo = _build_service()
        await svc.retrieve("query")
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["k"] == 5

    async def test_retrieve_custom_k(self) -> None:
        svc, _, mock_repo = _build_service()
        await svc.retrieve("query", k=10)
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["k"] == 10

    async def test_returns_result_objects(self) -> None:
        svc, _, _ = _build_service([_SAMPLE_RESULT])
        results = await svc.retrieve("test")
        assert results[0].ticker == "NESN"
        assert results[0].similarity == 0.89
