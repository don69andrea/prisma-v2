"""Integrationstests für GET /api/v1/fonds und POST /api/v1/fonds/vergleich."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.fonds_vergleich_service import FondsVergleichService
from backend.domain.value_objects.fonds_vergleich import (
    FondsVergleich,
    PortfolioCompareMetrics,
)
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.routers.fonds_vergleich import _get_service

pytestmark = pytest.mark.integration


def _mock_service() -> FondsVergleichService:
    svc = MagicMock(spec=FondsVergleichService)
    svc.list_fonds.return_value = [
        {"name": "VIAC Global 100", "description": "100% Aktien", "equity_ratio": 1.0}
    ]
    svc.compare = AsyncMock(
        return_value=FondsVergleich(
            fonds_name="VIAC Global 100",
            fonds_metrics=PortfolioCompareMetrics(
                expected_return_pa=Decimal("0.08"),
                volatility_pa=Decimal("0.18"),
                sharpe_ratio=Decimal("0.44"),
                max_drawdown=Decimal("-0.35"),
            ),
            custom_metrics=PortfolioCompareMetrics(
                expected_return_pa=Decimal("0.10"),
                volatility_pa=Decimal("0.20"),
                sharpe_ratio=Decimal("0.50"),
                max_drawdown=Decimal("-0.30"),
            ),
            snapshot_date=date(2026, 6, 9),
        )
    )
    return svc


@pytest.fixture
def app() -> Any:
    application = create_app()
    application.dependency_overrides[_get_service] = _mock_service
    return application


@pytest.mark.asyncio
async def test_list_fonds_returns_200(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/fonds")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "VIAC Global 100"
    assert "equity_ratio" in data[0]


@pytest.mark.asyncio
async def test_vergleich_returns_metrics(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/fonds/vergleich",
            json={
                "fonds_name": "VIAC Global 100",
                "positions": [
                    {"ticker": "NESN", "weight": 0.5},
                    {"ticker": "NOVN", "weight": 0.5},
                ],
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fonds_name"] == "VIAC Global 100"
    assert "fonds_metrics" in data
    assert "custom_metrics" in data
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_vergleich_unknown_fonds_returns_404(app: Any) -> None:
    from backend.application.services.fonds_vergleich_service import FondsNotFound

    broken_svc = MagicMock(spec=FondsVergleichService)
    broken_svc.list_fonds.return_value = []
    broken_svc.compare = AsyncMock(side_effect=FondsNotFound("UNBEKANNT"))

    application = create_app()
    application.dependency_overrides[_get_service] = lambda: broken_svc

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/fonds/vergleich",
            json={
                "fonds_name": "UNBEKANNT",
                "positions": [{"ticker": "NESN", "weight": 1.0}],
            },
        )
    assert resp.status_code == 404
