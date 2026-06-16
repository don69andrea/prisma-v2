"""Unit-Tests für NewsRetrievalService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.application.services.news_retrieval_service import NewsRetrievalService
from backend.domain.entities.news_retrieval_result import NewsRetrievalResult
from backend.domain.repositories.news_repository import NewsRepository

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)

_SAMPLE_RESULT = NewsRetrievalResult(
    chunk_id=uuid4(),
    news_document_id=uuid4(),
    chunk_idx=0,
    content="Nestlé verbucht Rekordumsatz im zweiten Quartal.",
    similarity=0.93,
    title="NESN Q2 Ergebnisse",
    source="NZZ",
    tickers=("NESN",),
    published_at=_NOW,
    metadata={},
)


def _build_service(
    retrieval_results: list[NewsRetrievalResult] | None = None,
    embedding: list[float] | None = None,
) -> tuple[NewsRetrievalService, AsyncMock, AsyncMock]:
    mock_repo = AsyncMock(spec=NewsRepository)
    mock_repo.find_nearest.return_value = retrieval_results or []

    mock_llm = AsyncMock()
    mock_llm.embed.return_value = [embedding or [0.1] * 1024]

    svc = NewsRetrievalService(news_repo=mock_repo, llm_client=mock_llm)
    return svc, mock_repo, mock_llm


class TestNewsRetrievalServiceRetrieve:
    async def test_returns_results_from_repository(self) -> None:
        svc, _, _ = _build_service(retrieval_results=[_SAMPLE_RESULT])

        results = await svc.retrieve("Nestlé Umsatz", k=5)

        assert len(results) == 1
        assert results[0].similarity == 0.93

    async def test_calls_llm_embed_with_query(self) -> None:
        svc, _, mock_llm = _build_service()

        await svc.retrieve("NESN Dividende", k=3)

        mock_llm.embed.assert_called_once()
        call_kwargs = mock_llm.embed.call_args
        texts_arg = call_kwargs[1].get("texts") or call_kwargs[0][0]
        assert "NESN Dividende" in texts_arg

    async def test_passes_embedding_to_repo(self) -> None:
        embedding = [0.5] * 1024
        svc, mock_repo, _ = _build_service(embedding=embedding)

        await svc.retrieve("test query", k=5)

        mock_repo.find_nearest.assert_called_once()
        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["query_embedding"] == embedding

    async def test_passes_k_to_repository(self) -> None:
        svc, mock_repo, _ = _build_service()

        await svc.retrieve("test", k=7)

        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["k"] == 7

    async def test_k_capped_at_max_20(self) -> None:
        svc, mock_repo, _ = _build_service()

        await svc.retrieve("test", k=50)

        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["k"] == 20

    async def test_k_at_boundary_20_not_reduced(self) -> None:
        svc, mock_repo, _ = _build_service()

        await svc.retrieve("test", k=20)

        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["k"] == 20

    async def test_default_k_is_5(self) -> None:
        svc, mock_repo, _ = _build_service()

        await svc.retrieve("test")

        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["k"] == 5

    async def test_ticker_filter_passed_to_repository(self) -> None:
        svc, mock_repo, _ = _build_service()

        await svc.retrieve("dividende", k=5, ticker="NESN")

        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["ticker"] == "NESN"

    async def test_no_ticker_filter_passes_none_to_repository(self) -> None:
        svc, mock_repo, _ = _build_service()

        await svc.retrieve("test", k=5)

        call_kwargs = mock_repo.find_nearest.call_args[1]
        assert call_kwargs["ticker"] is None

    async def test_empty_repository_returns_empty_list(self) -> None:
        svc, _, _ = _build_service(retrieval_results=[])

        results = await svc.retrieve("test", k=5)

        assert results == []

    async def test_no_embedding_returned_skips_repo_call(self) -> None:
        mock_repo = AsyncMock(spec=NewsRepository)
        mock_llm = AsyncMock()
        mock_llm.embed.return_value = []  # empty embeddings list

        svc = NewsRetrievalService(news_repo=mock_repo, llm_client=mock_llm)

        results = await svc.retrieve("test", k=5)

        assert results == []
        mock_repo.find_nearest.assert_not_called()

    async def test_repository_exception_propagates(self) -> None:
        mock_repo = AsyncMock(spec=NewsRepository)
        mock_repo.find_nearest.side_effect = RuntimeError("pgvector unavailable")
        mock_llm = AsyncMock()
        mock_llm.embed.return_value = [[0.1] * 1024]

        svc = NewsRetrievalService(news_repo=mock_repo, llm_client=mock_llm)

        with pytest.raises(RuntimeError, match="pgvector unavailable"):
            await svc.retrieve("test", k=5)

    async def test_llm_exception_propagates(self) -> None:
        mock_repo = AsyncMock(spec=NewsRepository)
        mock_llm = AsyncMock()
        mock_llm.embed.side_effect = ConnectionError("LLM unreachable")

        svc = NewsRetrievalService(news_repo=mock_repo, llm_client=mock_llm)

        with pytest.raises(ConnectionError, match="LLM unreachable"):
            await svc.retrieve("test", k=5)

    async def test_multiple_results_returned(self) -> None:
        second_result = NewsRetrievalResult(
            chunk_id=uuid4(),
            news_document_id=uuid4(),
            chunk_idx=1,
            content="ABB meldet Auftragseingang.",
            similarity=0.78,
            title="ABB Q1",
            source="Handelszeitung",
            tickers=("ABBN",),
            published_at=_NOW,
            metadata={},
        )
        svc, _, _ = _build_service(retrieval_results=[_SAMPLE_RESULT, second_result])

        results = await svc.retrieve("Quartalsbericht", k=5)

        assert len(results) == 2
        assert results[0].tickers == ("NESN",)
        assert results[1].tickers == ("ABBN",)

    async def test_embed_called_with_correct_model_and_feature(self) -> None:
        svc, _, mock_llm = _build_service()

        await svc.retrieve("test query", k=3)

        call_kwargs = mock_llm.embed.call_args[1]
        assert call_kwargs.get("model") == "voyage-3-large"
        assert call_kwargs.get("feature") == "news_rag_retrieval"
