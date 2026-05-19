"""Unit-Tests für RetrievalService mit gemocktem Repository + LLMClient."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.services.retrieval_service import _MAX_K, RetrievalService
from backend.domain.repositories.embedding_repository import RetrievalResult

pytestmark = pytest.mark.unit

_FAKE_EMBEDDING = [0.1] * 2048


def _make_result(ticker: str = "AAPL", similarity: float = 0.9) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_idx=0,
        content="Apple revenue grew 12% year-over-year.",
        similarity=similarity,
        ticker=ticker,
        doc_type="10-K",
    )


def _make_service() -> tuple[RetrievalService, MagicMock, MagicMock]:
    mock_repo = MagicMock()
    mock_repo.find_nearest = AsyncMock(return_value=[])
    mock_llm = MagicMock()
    mock_llm.embed = AsyncMock(return_value=[_FAKE_EMBEDDING])
    service = RetrievalService(embedding_repo=mock_repo, llm_client=mock_llm)
    return service, mock_repo, mock_llm


class TestRetrieve:
    async def test_calls_embed_with_query_text(self) -> None:
        service, _, mock_llm = _make_service()
        await service.retrieve(query="Apple revenue")
        mock_llm.embed.assert_called_once_with(
            texts=["Apple revenue"], model="voyage-3-large", feature="rag_retrieval"
        )

    async def test_calls_find_nearest_with_embedding(self) -> None:
        service, mock_repo, _ = _make_service()
        await service.retrieve(query="Apple revenue", k=3)
        mock_repo.find_nearest.assert_called_once_with(
            query_embedding=_FAKE_EMBEDDING, k=3, ticker=None
        )

    async def test_passes_ticker_filter(self) -> None:
        service, mock_repo, _ = _make_service()
        await service.retrieve(query="revenue", ticker="MSFT")
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["ticker"] == "MSFT"

    async def test_clamps_k_to_max(self) -> None:
        service, mock_repo, _ = _make_service()
        await service.retrieve(query="revenue", k=999)
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["k"] == _MAX_K

    async def test_returns_results_from_repo(self) -> None:
        service, mock_repo, _ = _make_service()
        expected = [_make_result("AAPL", 0.95), _make_result("AAPL", 0.80)]
        mock_repo.find_nearest.return_value = expected

        result = await service.retrieve(query="revenue")

        assert result == expected

    async def test_default_k_is_five(self) -> None:
        service, mock_repo, _ = _make_service()
        await service.retrieve(query="anything")
        call_kwargs = mock_repo.find_nearest.call_args.kwargs
        assert call_kwargs["k"] == 5
