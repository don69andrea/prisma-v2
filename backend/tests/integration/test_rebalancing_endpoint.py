"""Integrationstests für POST /api/v1/portfolio/rebalance."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.domain.entities.swiss_stock import SwissStock
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_swiss_stock_repository

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

_NOVN = SwissStock(
    id=uuid4(),
    ticker="NOVN",
    isin="CH0012005267",
    name="Novartis AG",
    exchange="XSWX",
    sector="Health Care",
    market_cap_chf=Decimal("180_000_000_000"),
)

_ABBN = SwissStock(
    id=uuid4(),
    ticker="ABBN",
    isin="CH0012221716",
    name="ABB Ltd",
    exchange="XSWX",
    sector="Industrials",
    market_cap_chf=Decimal("90_000_000_000"),
)

_KNOWN_STOCKS = {"NESN": _NESN, "NOVN": _NOVN, "ABBN": _ABBN}


@pytest.fixture
def mock_swiss_stock_repo() -> AsyncMock:
    repo = AsyncMock()

    async def _get_by_ticker(ticker: str) -> SwissStock | None:
        return _KNOWN_STOCKS.get(ticker.upper())

    repo.get_by_ticker = _get_by_ticker
    return repo


@pytest.fixture
def app(mock_swiss_stock_repo: AsyncMock) -> Any:
    application = create_app()
    application.dependency_overrides[get_swiss_stock_repository] = lambda: mock_swiss_stock_repo
    return application


@pytest.mark.asyncio
async def test_rebalance_returns_200_with_steps(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": 100_000,
                "current_weights": {"NESN": 0.30, "NOVN": 0.30},
                "target_weights": {"NESN": 0.40, "NOVN": 0.20, "ABBN": 0.10},
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_id" in data
    assert "steps" in data
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) == 3


@pytest.mark.asyncio
async def test_rebalance_buy_sell_hold_actions(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": 50_000,
                "current_weights": {"NESN": 0.30, "NOVN": 0.50},
                "target_weights": {"NESN": 0.50, "NOVN": 0.30},
            },
        )
    assert resp.status_code == 200
    steps = {s["ticker"]: s["action"] for s in resp.json()["steps"]}
    assert steps["NESN"] == "BUY"
    assert steps["NOVN"] == "SELL"


@pytest.mark.asyncio
async def test_rebalance_total_cost_in_response(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": 10_000,
                "current_weights": {"NESN": 0.10},
                "target_weights": {"NESN": 0.20},
                "transaction_cost_rate": 0.001,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    # delta=0.10, estimated_value=1000 CHF, cost=1000*0.001=1.0 CHF
    assert data["total_transaction_cost_chf"] == pytest.approx(1.0, abs=0.01)
    assert data["total_portfolio_value_chf"] == 10_000.0


@pytest.mark.asyncio
async def test_rebalance_invalid_portfolio_value_returns_422(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": -1000,
                "current_weights": {},
                "target_weights": {"NESN": 0.50},
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rebalance_3a_flag_in_response(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": 20_000,
                "current_weights": {"NESN": 0.40},
                "target_weights": {"NESN": 0.40},
                "is_3a_account": True,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_3a_account"] is True
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_rebalance_unknown_ticker_returns_422(app: Any) -> None:
    """W-9 / F-PORT-4: Frei erfundene Ticker (z.B. "FAKE0") dürfen nicht mit
    HTTP 200 verarbeitet werden, inkl. falschem is_3a_eligible-Default."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": 100_000,
                "current_weights": {"NESN": 0.50, "FAKE0": 0.50},
                "target_weights": {"NESN": 0.50, "FAKE0": 0.50},
            },
        )
    assert resp.status_code == 422
    data = resp.json()
    assert "FAKE0" in str(data["detail"])


@pytest.mark.asyncio
async def test_rebalance_many_unknown_tickers_returns_422_with_full_list(app: Any) -> None:
    """Realistischeres Szenario aus dem Audit: Mix bekannter und vieler
    erfundener Ticker — alle unbekannten Ticker müssen in der Antwort stehen."""
    current_weights = {"NESN": 0.50, "NOVN": 0.30, "ABBN": 0.10}
    fake_tickers = {f"FAKE{i}": 0.005 for i in range(20)}
    current_weights.update(fake_tickers)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/portfolio/rebalance",
            json={
                "total_portfolio_value_chf": 100_000,
                "current_weights": current_weights,
                "target_weights": current_weights,
            },
        )
    assert resp.status_code == 422
    detail = str(resp.json()["detail"])
    for ticker in fake_tickers:
        assert ticker in detail
