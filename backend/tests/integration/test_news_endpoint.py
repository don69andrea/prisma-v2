"""Integration-Tests für News-RAG-Endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.news_ingestion_service import NewsIngestionService
from backend.application.services.news_retrieval_service import NewsRetrievalService
from backend.domain.entities.news_retrieval_result import NewsRetrievalResult
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import (
    get_news_ingestion_service,
    get_news_retrieval_service,
)

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 6, 8, 7, 0, tzinfo=UTC)

_SAMPLE_RESULT = NewsRetrievalResult(
    chunk_id=__import__("uuid").uuid4(),
    news_document_id=__import__("uuid").uuid4(),
    chunk_idx=0,
    content="NESN verbucht Rekordumsatz.",
    similarity=0.92,
    title="NESN Quartalsgewinn",
    url="https://www.nzz.ch/finanzen/nesn-quartalsgewinn",
    source="NZZ",
    tickers=("NESN",),
    published_at=_NOW,
    metadata={},
)


@pytest.fixture
def mock_ingestion_service() -> AsyncMock:
    svc = AsyncMock(spec=NewsIngestionService)
    svc.ingest_all.return_value = {"ingested": 2, "skipped_duplicate": 1, "errors": 0}
    return svc


@pytest.fixture
def mock_retrieval_service() -> AsyncMock:
    svc = AsyncMock(spec=NewsRetrievalService)
    svc.retrieve.return_value = [_SAMPLE_RESULT]
    return svc


@pytest.fixture
def app(mock_ingestion_service: Any, mock_retrieval_service: Any) -> Any:
    application = create_app()
    application.dependency_overrides[get_news_ingestion_service] = lambda: mock_ingestion_service
    application.dependency_overrides[get_news_retrieval_service] = lambda: mock_retrieval_service
    return application


@pytest.mark.asyncio
async def test_news_ingest_returns_stats(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/news/ingest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested"] == 2
    assert data["skipped_duplicate"] == 1
    assert data["errors"] == 0


@pytest.mark.asyncio
async def test_news_retrieve_returns_results(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/news/retrieve", json={"query": "NESN Gewinn", "k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    result = data["results"][0]
    assert result["source"] == "NZZ"
    assert "NESN" in result["tickers"]
    assert result["similarity"] == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_news_retrieve_validation_empty_query(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/news/retrieve", json={"query": "", "k": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_news_retrieve_validation_k_too_large(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/news/retrieve", json={"query": "test", "k": 21})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_news_retrieve_with_ticker_filter(app: Any, mock_retrieval_service: Any) -> None:
    mock_retrieval_service.retrieve.return_value = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/news/retrieve", json={"query": "Nestlé", "k": 3, "ticker": "NESN"}
        )
    assert resp.status_code == 200
    mock_retrieval_service.retrieve.assert_called_once_with(query="Nestlé", k=3, ticker="NESN")
