"""Integrationstests für POST /api/v1/portfolio/rebalance."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from backend.interfaces.rest.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def app() -> Any:
    return create_app()


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
