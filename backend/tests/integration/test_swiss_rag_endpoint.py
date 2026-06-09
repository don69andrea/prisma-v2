"""Integration-Tests für POST /api/v1/rag/swiss/retrieve."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.swiss_filing_retrieval_service import (
    SwissFilingRetrievalService,
)
from backend.domain.entities.swiss_filing_retrieval_result import SwissFilingRetrievalResult
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_swiss_filing_retrieval_service

pytestmark = pytest.mark.integration

_SAMPLE = SwissFilingRetrievalResult(
    chunk_id=uuid4(),
    chunk_idx=0,
    url="https://example.com/nesn-annual-2023.pdf",
    ticker="NESN",
    source="IR",
    language="en",
    filing_date=date(2024, 3, 14),
    doc_type="Annual Report",
    content="Nestlé full-year 2023 organic growth was 7.2%.",
    similarity=0.91,
    metadata={"source": "IR"},
)


@pytest.fixture
def mock_retrieval_service() -> Any:
    svc = AsyncMock(spec=SwissFilingRetrievalService)
    svc.retrieve.return_value = [_SAMPLE]
    return svc


@pytest.fixture
def app(mock_retrieval_service: Any) -> Any:
    application = create_app()
    application.dependency_overrides[get_swiss_filing_retrieval_service] = lambda: (
        mock_retrieval_service
    )
    return application


@pytest.mark.asyncio
async def test_swiss_retrieve_ok(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/rag/swiss/retrieve",
            json={"query": "Nestlé Jahresbericht 2023 Umsatz", "k": 3},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["ticker"] == "NESN"
    assert data["results"][0]["similarity"] == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_swiss_retrieve_with_ticker_filter(app: Any, mock_retrieval_service: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/rag/swiss/retrieve",
            json={"query": "dividende", "k": 5, "ticker": "NESN"},
        )
    mock_retrieval_service.retrieve.assert_called_once_with(
        query="dividende", k=5, ticker="NESN", language=None
    )


@pytest.mark.asyncio
async def test_swiss_retrieve_with_language_filter(app: Any, mock_retrieval_service: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/rag/swiss/retrieve",
            json={"query": "Jahresbericht", "language": "de"},
        )
    call_kwargs = mock_retrieval_service.retrieve.call_args.kwargs
    assert call_kwargs["language"] == "de"


@pytest.mark.asyncio
async def test_swiss_retrieve_invalid_language(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/rag/swiss/retrieve",
            json={"query": "test", "language": "xx"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_swiss_retrieve_empty_query(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/rag/swiss/retrieve",
            json={"query": "ab"},  # too short (min_length=3)
        )
    assert resp.status_code == 422
