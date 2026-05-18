"""Integrationstests für GET /api/v1/stocks/{ticker}/prices."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.application.services.stock_service import StockService
from backend.domain.entities.stock import Stock
from backend.domain.repositories.stock_repository import StockRepository
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_stock_service

pytestmark = pytest.mark.integration

_AAPL_ID = uuid.uuid4()
_AAPL = Stock(
    id=_AAPL_ID,
    ticker="AAPL",
    name="Apple Inc.",
    isin="US0378331005",
    sector="Technology",
    country="US",
    currency="USD",
)


class _FakeStockRepo(StockRepository):
    def __init__(self, stocks: list[Stock]) -> None:
        self._by_ticker = {s.ticker: s for s in stocks}
        self._by_id = {s.id: s for s in stocks}

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        return self._by_ticker.get(ticker.upper())

    async def get(self, stock_id: UUID) -> Stock | None:
        return self._by_id.get(stock_id)

    async def list_by_ids(self, stock_ids: list[UUID]) -> list[Stock]:
        return [self._by_id[i] for i in stock_ids if i in self._by_id]

    async def list_by_tickers(self, tickers: list[str]) -> list[Stock]:
        return [self._by_ticker[t.upper()] for t in tickers if t.upper() in self._by_ticker]

    async def list(self, limit: int, offset: int) -> list[Stock]:
        return sorted(self._by_ticker.values(), key=lambda s: s.ticker)[offset : offset + limit]


def _make_app(stocks: list[Stock]) -> Any:
    app = create_app()
    stock_repo = _FakeStockRepo(stocks)
    provider = StubMarketDataProvider()
    app.dependency_overrides[get_stock_service] = lambda: StockService(
        repository=stock_repo,
        market_data_provider=provider,
    )
    return app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = _make_app([_AAPL])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def test_prices_known_ticker_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/AAPL/prices")
    assert response.status_code == 200


async def test_prices_default_returns_252_points(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/stocks/AAPL/prices")).json()
    assert body["ticker"] == "AAPL"
    assert len(body["prices"]) == 252
    assert "date" in body["prices"][0]
    assert "close" in body["prices"][0]


async def test_prices_unknown_ticker_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/UNKNOWN/prices")
    assert response.status_code == 404


async def test_prices_days_param_out_of_range_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/AAPL/prices?days=999")
    assert response.status_code == 422


async def test_prices_custom_days_returns_correct_length(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/stocks/AAPL/prices?days=10")).json()
    assert len(body["prices"]) == 10


async def test_prices_ticker_case_insensitive(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/aapl/prices")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"
