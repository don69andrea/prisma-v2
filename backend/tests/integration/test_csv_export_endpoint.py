"""Integrationstests für GET /api/v1/runs/{run_id}/export?format=csv."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.ranking_run_service import RankingRunNotFound, RankingRunService
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_ranking_run_service

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


def _make_service(rankings: list[Any]) -> RankingRunService:
    svc = AsyncMock(spec=RankingRunService)
    svc.get_rankings = AsyncMock(return_value=rankings)
    return svc


def _make_service_not_found() -> RankingRunService:
    svc = AsyncMock(spec=RankingRunService)
    svc.get_rankings = AsyncMock(side_effect=RankingRunNotFound(str(_RUN_ID)))
    return svc


@pytest.fixture
def app_with_rankings() -> Any:
    mock = _make_service(_RANKINGS)
    application = create_app()
    application.dependency_overrides[get_ranking_run_service] = lambda: mock
    return application


@pytest.fixture
def app_not_found() -> Any:
    mock = _make_service_not_found()
    application = create_app()
    application.dependency_overrides[get_ranking_run_service] = lambda: mock
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
    assert "weighted_avg" in header
    assert "is_sweet_spot" in header
    # NESN is rank 1 — should appear in first data row
    assert "NESN" in lines[1]
    assert "true" in lines[1]
    assert "NOVN" in lines[2]
    assert "false" in lines[2]


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
