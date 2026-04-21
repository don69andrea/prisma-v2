"""Integrationstests für GET /api/v1/stocks gegen die Test-App mit InMemory-Repository."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_stocks_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks")
    assert response.status_code == 200


async def test_stocks_response_has_items_and_total(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks")
    body = response.json()
    assert "items" in body
    assert "total" in body


async def test_stocks_returns_sample_data(http_client: AsyncClient) -> None:
    """Das InMemory-Repository in conftest.py enthält drei vorgeladene Stocks."""
    response = await http_client.get("/api/v1/stocks")
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_stocks_items_sorted_by_ticker(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks")
    tickers = [item["ticker"] for item in response.json()["items"]]
    assert tickers == sorted(tickers)


async def test_stocks_item_has_expected_fields(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks")
    item = response.json()["items"][0]
    assert "id" in item
    assert "ticker" in item
    assert "name" in item
    assert "currency" in item


async def test_stocks_limit_query_param(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks", params={"limit": 1})
    body = response.json()
    assert len(body["items"]) == 1


async def test_stocks_offset_query_param(http_client: AsyncClient) -> None:
    # Sample data has 3 stocks (AAPL, NESN, NOVN sorted); offset=2 returns last one
    response = await http_client.get(
        "/api/v1/stocks", params={"limit": 10, "offset": 2}
    )
    body = response.json()
    assert len(body["items"]) == 1


async def test_stocks_limit_exceeds_max_returns_422(http_client: AsyncClient) -> None:
    """FastAPI Query-Validierung: limit > 200 soll 422 Unprocessable Entity liefern."""
    response = await http_client.get("/api/v1/stocks", params={"limit": 201})
    assert response.status_code == 422


async def test_stocks_negative_offset_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/stocks", params={"offset": -1})
    assert response.status_code == 422
