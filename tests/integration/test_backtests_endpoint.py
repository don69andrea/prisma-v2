"""Integrationstests für /api/v1/backtests Endpunkte."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.backtest_service import BacktestService
from backend.domain.entities.backtest_result import BacktestResult, BacktestSeries, PortfolioMetrics
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_backtest_service

FAKE_METRICS = PortfolioMetrics(
    total_return=Decimal("0.10"),
    cagr=Decimal("0.10"),
    annual_vol=Decimal("0.15"),
    sharpe=Decimal("0.67"),
    max_drawdown=Decimal("0.05"),
)

FAKE_RESULT_ID = uuid4()
FAKE_RUN_ID = uuid4()

FAKE_RESULT = BacktestResult(
    id=FAKE_RESULT_ID,
    model_run_id=FAKE_RUN_ID,
    start_date=date(2025, 1, 1),
    end_date=date(2025, 12, 31),
    top_n=3,
    benchmark_ticker="^SSMI",
    prisma_metrics=FAKE_METRICS,
    universe_metrics=FAKE_METRICS,
    benchmark_metrics=FAKE_METRICS,
    series=BacktestSeries(
        dates=[date(2025, 1, 31)],
        prisma=[Decimal("1.01")],
        universe=[Decimal("1.008")],
        benchmark=[Decimal("1.005")],
    ),
    created_at=datetime.now(tz=timezone.utc),
)


@pytest.fixture
def mock_service() -> BacktestService:
    svc = AsyncMock(spec=BacktestService)
    svc.run_backtest.return_value = FAKE_RESULT
    svc.get_backtest_result.return_value = FAKE_RESULT
    return svc


@pytest.fixture
def app(mock_service):
    application = create_app()
    application.dependency_overrides[get_backtest_service] = lambda: mock_service
    return application


@pytest.mark.asyncio
async def test_post_backtest_returns_200_with_result(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtests",
            json={
                "model_run_id": str(FAKE_RUN_ID),
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "top_n": 3,
                "benchmark_ticker": "^SSMI",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "series" in data
    assert "prisma_metrics" in data
    assert "universe_metrics" in data
    assert "benchmark_metrics" in data


@pytest.mark.asyncio
async def test_get_backtest_by_id_returns_200(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/backtests/{FAKE_RESULT_ID}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(FAKE_RESULT_ID)


@pytest.mark.asyncio
async def test_get_backtest_by_id_returns_404_when_not_found(app, mock_service):
    mock_service.get_backtest_result.return_value = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/backtests/{uuid4()}")
    assert resp.status_code == 404
