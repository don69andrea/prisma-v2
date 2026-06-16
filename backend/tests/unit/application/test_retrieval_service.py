"""Unit-Tests für RetrievalService."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.application.services.retrieval_service import RetrievalService
from backend.domain.entities.retrieval_result import RetrievalResult
from backend.domain.repositories.embedding_repository import EmbeddingRepository


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock(spec=EmbeddingRepository)


@pytest.fixture
def mock_llm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock, mock_llm: AsyncMock) -> RetrievalService:
    return RetrievalService(embedding_repo=mock_repo, llm_client=mock_llm)


class TestRetrievalService:
    @pytest.mark.asyncio
    async def test_retrieve_basic(
        self: "TestRetrievalService",
        service: RetrievalService,
        mock_repo: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        mock_llm.embed.return_value = [[0.1] * 1024]
        mock_repo.find_nearest.return_value = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                chunk_idx=0,
                content="Apple",
                similarity=0.95,
                ticker="AAPL",
                doc_type="10-K",
            )
        ]
        results = await service.retrieve("Apple", k=5)
        assert len(results) == 1 and results[0].similarity == 0.95

    @pytest.mark.asyncio
    async def test_k_capped(
        self: "TestRetrievalService",
        service: RetrievalService,
        mock_repo: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        mock_llm.embed.return_value = [[0.0] * 1024]
        mock_repo.find_nearest.return_value = []
        await service.retrieve("test", k=50)
        assert mock_repo.find_nearest.call_args[1]["k"] == 20

    @pytest.mark.asyncio
    async def test_no_embedding(
        self: "TestRetrievalService",
        service: RetrievalService,
        mock_repo: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        mock_llm.embed.return_value = []
        results = await service.retrieve("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_multiple_results(
        self: "TestRetrievalService",
        service: RetrievalService,
        mock_repo: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        mock_llm.embed.return_value = [[0.0] * 1024]
        mock_repo.find_nearest.return_value = [
            RetrievalResult(uuid4(), uuid4(), 0, "c1", 0.95, "AAPL", "10-K"),
            RetrievalResult(uuid4(), uuid4(), 1, "c2", 0.87, "AAPL", "10-Q"),
        ]
        results = await service.retrieve("test", k=5)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_default_k(
        self: "TestRetrievalService",
        service: RetrievalService,
        mock_repo: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        mock_llm.embed.return_value = [[0.0] * 1024]
        mock_repo.find_nearest.return_value = []
        await service.retrieve("test")
        assert mock_repo.find_nearest.call_args[1]["k"] == 5

    @pytest.mark.asyncio
    async def test_ticker_filter(
        self: "TestRetrievalService",
        service: RetrievalService,
        mock_repo: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        mock_llm.embed.return_value = [[0.0] * 1024]
        mock_repo.find_nearest.return_value = []
        await service.retrieve("test", ticker="AAPL")
        assert mock_repo.find_nearest.call_args[1]["ticker"] == "AAPL"
