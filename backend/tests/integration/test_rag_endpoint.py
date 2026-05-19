"""Integrationstests für POST /api/v1/rag/retrieve mit gemocktem RetrievalService."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.application.services.retrieval_service import RetrievalService
from backend.domain.repositories.embedding_repository import RetrievalResult
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_retrieval_service

pytestmark = pytest.mark.integration

_DOC_ID = uuid.uuid4()
_CHUNK_ID = uuid.uuid4()


def _make_result(ticker: str = "AAPL", similarity: float = 0.92) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=_CHUNK_ID,
        document_id=_DOC_ID,
        chunk_idx=0,
        content="Apple reported record revenue of $123B.",
        similarity=similarity,
        ticker=ticker,
        doc_type="10-K",
    )


@pytest.fixture
def mock_retrieval_service() -> MagicMock:
    svc = MagicMock(spec=RetrievalService)
    svc.retrieve = AsyncMock(return_value=[_make_result()])
    return svc


@pytest_asyncio.fixture
async def http_client(
    mock_retrieval_service: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/rag/retrieve
# ---------------------------------------------------------------------------


async def test_retrieve_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/rag/retrieve",
        json={"query": "Apple revenue growth"},
    )
    assert response.status_code == 200


async def test_retrieve_response_shape(http_client: AsyncClient) -> None:
    body = (
        await http_client.post(
            "/api/v1/rag/retrieve",
            json={"query": "Apple revenue growth"},
        )
    ).json()
    assert "results" in body
    assert "total" in body


async def test_retrieve_result_fields(http_client: AsyncClient) -> None:
    body = (
        await http_client.post(
            "/api/v1/rag/retrieve",
            json={"query": "Apple revenue growth"},
        )
    ).json()
    r = body["results"][0]
    assert "chunk_id" in r
    assert "document_id" in r
    assert "chunk_idx" in r
    assert "content" in r
    assert "similarity" in r
    assert "ticker" in r
    assert "doc_type" in r


async def test_retrieve_total_matches_results_length(http_client: AsyncClient) -> None:
    body = (
        await http_client.post(
            "/api/v1/rag/retrieve",
            json={"query": "Apple revenue"},
        )
    ).json()
    assert body["total"] == len(body["results"])


async def test_retrieve_passes_k_to_service(
    http_client: AsyncClient, mock_retrieval_service: MagicMock
) -> None:
    await http_client.post(
        "/api/v1/rag/retrieve",
        json={"query": "margin", "k": 7},
    )
    mock_retrieval_service.retrieve.assert_called_once()
    assert mock_retrieval_service.retrieve.call_args.kwargs["k"] == 7


async def test_retrieve_passes_ticker_to_service(
    http_client: AsyncClient, mock_retrieval_service: MagicMock
) -> None:
    await http_client.post(
        "/api/v1/rag/retrieve",
        json={"query": "revenue", "ticker": "MSFT"},
    )
    assert mock_retrieval_service.retrieve.call_args.kwargs["ticker"] == "MSFT"


async def test_retrieve_empty_query_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/rag/retrieve",
        json={"query": ""},
    )
    assert response.status_code == 422


async def test_retrieve_k_above_max_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/rag/retrieve",
        json={"query": "anything", "k": 99},
    )
    assert response.status_code == 422


async def test_retrieve_k_zero_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/rag/retrieve",
        json={"query": "anything", "k": 0},
    )
    assert response.status_code == 422
