"""Integrationstests für GET /api/v1/stocks/{ticker}/dividends."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.domain.errors import SwissDataUnavailableError
from backend.domain.value_objects.dividend_data import DividendData, DividendEntry
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_yfinance_adapter

pytestmark = pytest.mark.integration

_NESN_DATA = DividendData(
    ticker="NESN",
    last_dividend_chf=2.90,
    ex_date="2025-04-14",
    dividend_yield_pct=3.1,
    history=(
        DividendEntry(date="2024-04-15", amount_chf=2.80),
        DividendEntry(date="2025-04-14", amount_chf=2.90),
    ),
    disclaimer=(
        "Dividendendaten via Yahoo Finance. Keine Anlageberatung. "
        "Historische Ausschüttungen garantieren keine zukünftigen Zahlungen."
    ),
)


def _make_adapter(data: DividendData) -> YFinanceSwissAdapter:
    adapter = AsyncMock(spec=YFinanceSwissAdapter)
    adapter.get_dividends = AsyncMock(return_value=data)
    return adapter


def _make_adapter_unavailable(ticker: str) -> YFinanceSwissAdapter:
    adapter = AsyncMock(spec=YFinanceSwissAdapter)
    adapter.get_dividends = AsyncMock(side_effect=SwissDataUnavailableError(ticker))
    return adapter


@pytest.fixture
def app_with_nesn() -> Any:
    mock = _make_adapter(_NESN_DATA)
    application = create_app()
    application.dependency_overrides[get_yfinance_adapter] = lambda: mock
    return application


@pytest.fixture
def app_with_unavailable() -> Any:
    mock = _make_adapter_unavailable("UNKN")
    application = create_app()
    application.dependency_overrides[get_yfinance_adapter] = lambda: mock
    return application


@pytest.mark.asyncio
async def test_dividends_returns_data(app_with_nesn: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_nesn), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stocks/NESN/dividends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["last_dividend_chf"] == 2.90
    assert data["ex_date"] == "2025-04-14"
    assert data["dividend_yield_pct"] == 3.1
    assert len(data["history"]) == 2
    assert data["history"][0]["date"] == "2024-04-15"
    assert data["history"][1]["amount_chf"] == 2.90
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_dividends_unknown_ticker_returns_404(app_with_unavailable: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_unavailable), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stocks/UNKN/dividends")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dividends_null_fields_allowed(app_with_nesn: Any) -> None:
    """None-Felder dürfen im Response vorkommen (yfinance liefert nicht immer alle Daten)."""
    null_data = DividendData(
        ticker="MINI",
        last_dividend_chf=None,
        ex_date=None,
        dividend_yield_pct=None,
        history=(),
        disclaimer="test",
    )
    mock = _make_adapter(null_data)
    application = create_app()
    application.dependency_overrides[get_yfinance_adapter] = lambda: mock
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stocks/MINI/dividends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MINI"
    assert data["last_dividend_chf"] is None
    assert data["history"] == []
