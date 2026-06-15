"""Integrationstests für GET /api/v1/stocks/{ticker}/3a-eligibility."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.entities.swiss_stock import SwissStock
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_swiss_market_service

pytestmark = pytest.mark.integration

_NESN = SwissStock(
    id=uuid4(),
    ticker="NESN",
    isin="CH0038863350",
    name="Nestlé SA",
    exchange="XSWX",
    sector="Consumer Staples",
    market_cap_chf=Decimal("245_000_000_000"),
)

_SMALL_STOCK = SwissStock(
    id=uuid4(),
    ticker="TINY",
    isin="CH0038863350",
    name="Tiny AG",
    exchange="XSWX",
    sector="Industrials",
    market_cap_chf=Decimal("10_000_000"),
)


@pytest.fixture
def mock_swiss_service_nesn() -> SwissMarketService:
    svc = AsyncMock(spec=SwissMarketService)
    svc.check_3a_eligibility.side_effect = None

    async def _check(ticker: str) -> Any:
        from backend.domain.services.eligibility_filter import EligibilityFilter

        stocks = {"NESN": _NESN, "TINY": _SMALL_STOCK}
        if ticker.upper() not in stocks:
            raise ValueError(f"Swiss Stock '{ticker.upper()}' nicht gefunden")
        return EligibilityFilter().check(stocks[ticker.upper()])

    svc.check_3a_eligibility = _check
    return svc


@pytest.fixture
def app(mock_swiss_service_nesn: SwissMarketService) -> Any:
    application = create_app()
    application.dependency_overrides[get_swiss_market_service] = lambda: mock_swiss_service_nesn
    return application


@pytest.mark.asyncio
async def test_eligible_stock_returns_true(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/NESN/3a-eligibility")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["eligible"] is True
    assert data["reasons"] == []


@pytest.mark.asyncio
async def test_ineligible_stock_returns_reasons(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/TINY/3a-eligibility")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "TINY"
    assert data["eligible"] is False
    assert "market_cap_too_low" in data["reasons"]


@pytest.mark.asyncio
async def test_unknown_ticker_returns_404(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/UNKN/3a-eligibility")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ticker_is_case_insensitive(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/nesn/3a-eligibility")
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "NESN"
