"""Integrationstests für GET /api/v1/stocks/{ticker}/fundamentals."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_fundamentals_known_ticker_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/fundamentals")
    assert response.status_code == 200


async def test_fundamentals_known_ticker_has_pe_ratio(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/fundamentals")
    body = response.json()
    assert body["pe_ratio"] == pytest.approx(28.0)
    assert body["pb_ratio"] == pytest.approx(45.0)


async def test_fundamentals_response_has_ticker_field(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/fundamentals")
    body = response.json()
    assert body["ticker"] == "AAPL"


async def test_fundamentals_response_has_disclaimer(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/fundamentals")
    body = response.json()
    assert "disclaimer" in body
    assert len(body["disclaimer"]) > 0


async def test_fundamentals_unknown_ticker_returns_404(http_client: AsyncClient) -> None:
    """Ticker nicht in Stock-DB → 404."""
    response = await http_client.get("/api/v1/stocks/UNKNOWN/fundamentals")
    assert response.status_code == 404


async def test_fundamentals_unknown_ticker_404_detail(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/XYZNOTFOUND/fundamentals")
    assert response.status_code == 404
    assert "XYZNOTFOUND" in response.json()["detail"]


async def test_fundamentals_null_fields_for_ticker_not_in_stub(
    http_client: AsyncClient,
) -> None:
    """NESN ist in der Stock-DB, aber nicht in StubFundamentalsProvider._DEMO_DATA
    → alle numerischen Felder null, aber 200 OK mit Disclaimer."""
    response = await http_client.get("/api/v1/stocks/NESN/fundamentals")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NESN"
    assert body["pe_ratio"] is None
    assert body["pb_ratio"] is None
    assert body["fcf_yield"] is None
    assert body["dividend_yield"] is None
    assert "disclaimer" in body


async def test_fundamentals_case_insensitive(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/aapl/fundamentals")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"
