"""Integrationstests für GET /api/v1/admin/costs.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §9 + §10.3.

Keine echte DB — get_cost_tracker wird mit einem FakeCostTracker überschrieben.
Auth wird durch den bypass_jwt_auth-Autouse-Fixture in integration/conftest.py
transparent bypassed (JWT-geschützter Router-Level-Check).
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.domain.cost_summary import (
    CallEntry,
    CostSummary,
    FeatureBreakdown,
    ModelBreakdown,
)
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_cost_tracker, get_stock_repository
from backend.tests.conftest import InMemoryStockRepository

_SAMPLE_SUMMARY = CostSummary(
    month="2026-04",
    cap_usd=Decimal("20.00"),
    current_usd=Decimal("5.50"),
    remaining_usd=Decimal("14.50"),
    by_model=[
        ModelBreakdown(model="claude-sonnet-4-6", calls=3, cost_usd=Decimal("4.50")),
        ModelBreakdown(model="claude-haiku-4-5", calls=5, cost_usd=Decimal("1.00")),
    ],
    by_feature=[
        FeatureBreakdown(feature="narrative_engine", calls=4, cost_usd=Decimal("3.00")),
        FeatureBreakdown(feature="screening", calls=4, cost_usd=Decimal("2.50")),
    ],
    last_calls=[
        CallEntry(
            created_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
            model="claude-sonnet-4-6",
            feature="narrative_engine",
            cost_usd=Decimal("1.50"),
        )
    ],
)


class FakeCostTracker:
    async def summary(self, *, last_n: int = 10) -> CostSummary:
        return _SAMPLE_SUMMARY


@pytest_asyncio.fixture
async def admin_http_client(
    in_memory_repo: InMemoryStockRepository,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient mit FakeCostTracker-Override. JWT-Auth wird durch den
    bypass_jwt_auth-Autouse-Fixture in conftest.py transparent übernommen."""
    app = create_app()
    app.dependency_overrides[get_stock_repository] = lambda: in_memory_repo
    app.dependency_overrides[get_cost_tracker] = lambda: FakeCostTracker()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestAdminCostsEndpoint:
    async def test_returns_200(self, admin_http_client: AsyncClient) -> None:
        response = await admin_http_client.get("/api/v1/admin/costs")
        assert response.status_code == 200

    async def test_response_matches_cost_summary_shape(
        self, admin_http_client: AsyncClient
    ) -> None:
        response = await admin_http_client.get("/api/v1/admin/costs")
        assert response.status_code == 200
        data = response.json()

        assert "month" in data
        assert "cap_usd" in data
        assert "current_usd" in data
        assert "remaining_usd" in data
        assert "by_model" in data
        assert "by_feature" in data
        assert "last_calls" in data

        assert isinstance(data["month"], str)
        assert isinstance(data["cap_usd"], float)
        assert data["month"] == "2026-04"
        assert data["cap_usd"] == 20.0
        assert data["current_usd"] == 5.5
        assert data["remaining_usd"] == 14.5
        assert len(data["by_model"]) == 2
        assert len(data["by_feature"]) == 2
        assert len(data["last_calls"]) == 1

    async def test_last_query_param_validates_range(self, admin_http_client: AsyncClient) -> None:
        response_zero = await admin_http_client.get("/api/v1/admin/costs?last=0")
        assert response_zero.status_code == 422

        response_over = await admin_http_client.get("/api/v1/admin/costs?last=101")
        assert response_over.status_code == 422

        response_ok = await admin_http_client.get("/api/v1/admin/costs?last=10")
        assert response_ok.status_code == 200
