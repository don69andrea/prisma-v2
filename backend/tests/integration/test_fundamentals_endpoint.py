"""Integrationstests für GET /api/v1/stocks/{ticker}/fundamentals."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.domain.errors import SwissDataUnavailableError
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_yfinance_adapter

pytestmark = pytest.mark.integration

_NESN_FUNDAMENTALS = SwissFundamentals(
    market_cap_chf=None,
    pe_ratio=22.5,
    pb_ratio=4.1,
    dividend_yield=0.031,
    eps_chf=4.80,
)


def _make_adapter(fundamentals: SwissFundamentals) -> YFinanceSwissAdapter:
    adapter = AsyncMock(spec=YFinanceSwissAdapter)
    adapter.get_fundamentals = AsyncMock(return_value=fundamentals)
    return adapter


def _make_adapter_unavailable() -> YFinanceSwissAdapter:
    adapter = AsyncMock(spec=YFinanceSwissAdapter)
    adapter.get_fundamentals = AsyncMock(side_effect=SwissDataUnavailableError("UNKN"))
    return adapter


@pytest.fixture
def app_with_data() -> Any:
    mock = _make_adapter(_NESN_FUNDAMENTALS)
    application = create_app()
    application.dependency_overrides[get_yfinance_adapter] = lambda: mock
    return application


@pytest.fixture
def app_unavailable() -> Any:
    mock = _make_adapter_unavailable()
    application = create_app()
    application.dependency_overrides[get_yfinance_adapter] = lambda: mock
    return application


@pytest.mark.asyncio
async def test_fundamentals_returns_data(app_with_data: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_data), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stocks/NESN/fundamentals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["pe_ratio"] == 22.5
    assert data["pb_ratio"] == 4.1
    assert data["eps_chf"] == 4.8
    assert data["dividend_yield_pct"] == 3.1
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_fundamentals_unknown_ticker_returns_404(app_unavailable: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_unavailable), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stocks/UNKN/fundamentals")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fundamentals_null_fields_allowed(app_with_data: Any) -> None:
    null_fundamentals = SwissFundamentals(
        market_cap_chf=None,
        pe_ratio=None,
        pb_ratio=None,
        dividend_yield=None,
        eps_chf=None,
    )
    mock = _make_adapter(null_fundamentals)
    application = create_app()
    application.dependency_overrides[get_yfinance_adapter] = lambda: mock
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stocks/TINY/fundamentals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pe_ratio"] is None
    assert data["pb_ratio"] is None
    assert data["eps_chf"] is None
    assert data["dividend_yield_pct"] is None
