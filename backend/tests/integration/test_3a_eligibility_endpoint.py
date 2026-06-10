"""Integrationstests für GET /api/v1/stocks/{ticker}/3a-eligibility."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_eligibility_ch_stock_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/NESN/3a-eligibility")
    assert response.status_code == 200


async def test_eligibility_ch_stock_is_eligible(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/NESN/3a-eligibility")
    body = response.json()
    assert body["eligible"] is True
    assert body["reasons"] == []


async def test_eligibility_us_stock_is_not_eligible(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/3a-eligibility")
    body = response.json()
    assert body["eligible"] is False


async def test_eligibility_us_stock_has_reason(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/3a-eligibility")
    body = response.json()
    assert len(body["reasons"]) > 0


async def test_eligibility_response_has_ticker_field(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/NESN/3a-eligibility")
    body = response.json()
    assert body["ticker"] == "NESN"


async def test_eligibility_response_has_disclaimer(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/AAPL/3a-eligibility")
    body = response.json()
    assert "disclaimer" in body
    assert len(body["disclaimer"]) > 0


async def test_eligibility_unknown_ticker_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/UNKNOWN/3a-eligibility")
    assert response.status_code == 404


async def test_eligibility_case_insensitive(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks/nesn/3a-eligibility")
    assert response.status_code == 200
    assert response.json()["ticker"] == "NESN"
