"""Integrationstests fuer GET /api/v1/runs/{run_id}/export?format=csv."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.ranking_run_service import RankingRunNotFound, RankingRunService
from backend.application.services.stock_service import StockService
from backend.domain.entities.stock import Stock
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_ranking_run_service, get_stock_service

pytestmark = pytest.mark.integration

_RUN_ID = uuid.uuid4()

_RANKINGS = [
    {
        "ticker": "NESN",
        "total_rank": 1,
        "weighted_avg": 5.4,
        "is_sweet_spot": True,
        "per_model_ranks": {"quality_classic": 1, "trend_momentum": 2},
    },
    {
        "ticker": "NOVN",
        "total_rank": 2,
        "weighted_avg": 4.8,
        "is_sweet_spot": False,
        "per_model_ranks": {"quality_classic": 2, "trend_momentum": 1},
    },
]

_STOCKS = {
    "NESN": Stock(
        id=uuid.uuid4(),
        ticker="NESN",
        name="Nestlé S.A.",
        sector="Consumer Staples",
        currency="CHF",
    ),
    "NOVN": Stock(
        id=uuid.uuid4(), ticker="NOVN", name="Novartis AG", sector="Healthcare", currency="CHF"
    ),
}


def _make_service(rankings: list[Any]) -> RankingRunService:
    svc = AsyncMock(spec=RankingRunService)
    svc.get_rankings = AsyncMock(return_value=rankings)
    return svc


def _make_service_not_found() -> RankingRunService:
    svc = AsyncMock(spec=RankingRunService)
    svc.get_rankings = AsyncMock(side_effect=RankingRunNotFound(_RUN_ID))
    return svc


def _make_stock_service() -> StockService:
    svc = AsyncMock(spec=StockService)

    async def _get(ticker: str) -> Stock | None:
        return _STOCKS.get(ticker.upper())

    svc.get_by_ticker = _get
    return svc


@pytest.fixture
def app_with_rankings() -> Any:
    application = create_app()
    application.dependency_overrides[get_ranking_run_service] = lambda: _make_service(_RANKINGS)
    application.dependency_overrides[get_stock_service] = lambda: _make_stock_service()
    return application


@pytest.fixture
def app_not_found() -> Any:
    application = create_app()
    application.dependency_overrides[get_ranking_run_service] = lambda: _make_service_not_found()
    application.dependency_overrides[get_stock_service] = lambda: _make_stock_service()
    return application


@pytest.mark.asyncio
async def test_csv_export_returns_text_csv(app_with_rankings: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_rankings), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/runs/{_RUN_ID}/export?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert f'filename="rankings_{_RUN_ID}.csv"' in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_csv_export_content(app_with_rankings: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_rankings), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/runs/{_RUN_ID}/export?format=csv")
    lines = resp.text.strip().splitlines()
    assert len(lines) == 3  # header + 2 rows
    header = lines[0]
    assert "rank" in header
    assert "ticker" in header
    assert "name" in header
    assert "sector" in header
    assert "weighted_avg" in header
    assert "is_sweet_spot" in header
    assert "NESN" in lines[1]
    assert "true" in lines[1]
    assert "NOVN" in lines[2]
    assert "false" in lines[2]


@pytest.mark.asyncio
async def test_csv_export_name_sector_enrichment(app_with_rankings: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_rankings), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/runs/{_RUN_ID}/export?format=csv")
    body = resp.text
    assert "Nestlé S.A." in body
    assert "Consumer Staples" in body


@pytest.mark.asyncio
async def test_csv_export_unknown_run_returns_404(app_not_found: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_not_found), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/runs/{_RUN_ID}/export?format=csv")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_csv_export_invalid_format_returns_422(app_with_rankings: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_rankings), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/runs/{_RUN_ID}/export?format=json")
    assert resp.status_code == 422
