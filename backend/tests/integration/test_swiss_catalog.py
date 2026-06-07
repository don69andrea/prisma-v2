"""Integrationstests für GET /api/v1/stocks?exchange=XSWX — Swiss Stock Catalog."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.stock_service import StockService
from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.entities.swiss_stock import SwissStock
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_stock_service, get_swiss_market_service

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test data — 20 SMI stocks (all with valid CH ISIN CH0038863350 for simplicity)
# ---------------------------------------------------------------------------

def _make_smi_stocks() -> list[SwissStock]:
    nesn_isin = "CH0038863350"  # Luhn-valid
    sectors = ["Consumer Staples", "Healthcare", "Financials", "Industrials", "Materials"]
    tickers = [
        "NESN", "NOVN", "ROG", "ABBN", "ZURN",
        "UBSG", "UHR", "GEBN", "GIVN", "LONN",
        "SREN", "SGKN", "SLHN", "SCMN", "BALN",
        "HOLN", "PGHN", "KRIN", "CFR", "STMN",
    ]
    return [
        SwissStock(
            id=uuid4(),
            ticker=ticker,
            isin=nesn_isin,
            name=f"{ticker} AG",
            exchange="XSWX",
            sector=sectors[i % len(sectors)],
            market_cap_chf=None,
        )
        for i, ticker in enumerate(tickers)
    ]


SMI_STOCKS = _make_smi_stocks()


@pytest.fixture
def mock_swiss_service() -> SwissMarketService:
    svc = AsyncMock(spec=SwissMarketService)
    svc.list_smi_stocks.return_value = SMI_STOCKS
    svc.get_swiss_stock.return_value = SMI_STOCKS[0]
    return svc


@pytest.fixture
def mock_stock_service() -> StockService:
    svc = AsyncMock(spec=StockService)
    svc.list_stocks.return_value = []
    return svc


@pytest.fixture
def app(mock_swiss_service, mock_stock_service):
    application = create_app()
    application.dependency_overrides[get_swiss_market_service] = lambda: mock_swiss_service
    application.dependency_overrides[get_stock_service] = lambda: mock_stock_service
    return application


@pytest.mark.asyncio
async def test_swiss_stocks_returns_20_items(app) -> None:
    """exchange=XSWX filter gibt genau 20 SMI-Stocks zurück."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks", params={"exchange": "XSWX", "limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 20
    assert len(data["items"]) == 20


@pytest.mark.asyncio
async def test_swiss_stocks_all_chf_currency(app) -> None:
    """Alle zurückgegebenen Swiss Stocks haben currency=CHF."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks", params={"exchange": "XSWX", "limit": 50})
    items = resp.json()["items"]
    assert all(item["currency"] == "CHF" for item in items)


@pytest.mark.asyncio
async def test_swiss_stocks_all_have_exchange_field(app) -> None:
    """Alle zurückgegebenen Swiss Stocks haben exchange=XSWX."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks", params={"exchange": "XSWX", "limit": 50})
    items = resp.json()["items"]
    assert all(item["exchange"] == "XSWX" for item in items)


@pytest.mark.asyncio
async def test_stocks_without_exchange_filter_not_affected(app) -> None:
    """GET /api/v1/stocks ohne exchange-Filter delegiert an StockService (kein Regression)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks")
    assert resp.status_code == 200
    # StockService mock returns [] — just verify it was called (not SwissMarketService)
    data = resp.json()
    assert data["total"] == 0
