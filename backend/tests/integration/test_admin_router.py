"""Integrationstests für GET /api/v1/admin/costs.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §9 + §10.3.

Keine echte DB — get_cost_tracker wird mit einem FakeCostTracker überschrieben.
Auth via X-API-Key (konstant-zeitsicher, hmac.compare_digest).
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.config import Settings, get_settings
from backend.domain.cost_summary import (
    CallEntry,
    CostSummary,
    FeatureBreakdown,
    ModelBreakdown,
)
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_cost_tracker, get_stock_repository
from backend.tests.conftest import InMemoryStockRepository

# Fester Test-API-Key — entkoppelt die Tests vom Production-Default in
# config.py. Tests senden diesen Key, der Override unten injiziert ihn
# in die FastAPI-Dependency-Chain.
_TEST_API_KEY = "test-admin-key-for-integration-tests"

# ---------------------------------------------------------------------------
# FakeCostTracker
# ---------------------------------------------------------------------------

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
    """Minimaler Stub, der summary() mit Fixture-Daten beantwortet."""

    async def summary(self, *, last_n: int = 10) -> CostSummary:
        return _SAMPLE_SUMMARY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_http_client(
    in_memory_repo: InMemoryStockRepository,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient mit FakeCostTracker-, InMemoryStockRepository- und
    Test-Settings-Overrides.

    Keine echte DB-Verbindung — geeignet für HTTP-Layer-Tests des Admin-Endpoints.
    Der Settings-Override garantiert, dass der API-Key-Auth-Pfad gegen einen
    festen Test-Key prüft, nicht gegen `.env` oder Production-Defaults.
    """
    app = create_app()

    test_settings = Settings(api_key=_TEST_API_KEY)

    app.dependency_overrides[get_stock_repository] = lambda: in_memory_repo
    app.dependency_overrides[get_cost_tracker] = lambda: FakeCostTracker()
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAdminCostsEndpoint:
    async def test_returns_401_without_api_key_header(self, admin_http_client: AsyncClient) -> None:
        """Request ohne X-API-Key muss 401 liefern."""
        response = await admin_http_client.get("/api/v1/admin/costs")
        assert response.status_code == 401

    async def test_returns_401_with_wrong_api_key(self, admin_http_client: AsyncClient) -> None:
        """Request mit falschem X-API-Key muss 401 liefern."""
        response = await admin_http_client.get(
            "/api/v1/admin/costs",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    async def test_returns_200_with_correct_api_key(self, admin_http_client: AsyncClient) -> None:
        """Request mit korrektem X-API-Key (Test-Override) muss 200 liefern."""
        response = await admin_http_client.get(
            "/api/v1/admin/costs",
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 200

    async def test_response_matches_cost_summary_shape(
        self, admin_http_client: AsyncClient
    ) -> None:
        """Response muss alle Top-Level-Keys mit korrekten Typen enthalten."""
        response = await admin_http_client.get(
            "/api/v1/admin/costs",
            headers={"X-API-Key": _TEST_API_KEY},
        )
        assert response.status_code == 200
        data = response.json()

        # Top-Level-Keys
        assert "month" in data
        assert "cap_usd" in data
        assert "current_usd" in data
        assert "remaining_usd" in data
        assert "by_model" in data
        assert "by_feature" in data
        assert "last_calls" in data

        # Typen
        assert isinstance(data["month"], str)
        assert isinstance(data["cap_usd"], float)
        assert isinstance(data["current_usd"], float)
        assert isinstance(data["remaining_usd"], float)
        assert isinstance(data["by_model"], list)
        assert isinstance(data["by_feature"], list)
        assert isinstance(data["last_calls"], list)

        # Werte aus _SAMPLE_SUMMARY
        assert data["month"] == "2026-04"
        assert data["cap_usd"] == 20.0
        assert data["current_usd"] == 5.5
        assert data["remaining_usd"] == 14.5
        assert len(data["by_model"]) == 2
        assert len(data["by_feature"]) == 2
        assert len(data["last_calls"]) == 1

    async def test_last_query_param_validates_range(self, admin_http_client: AsyncClient) -> None:
        """?last=0 und ?last=101 müssen 422 liefern; ?last=10 muss 200 liefern."""
        headers = {"X-API-Key": _TEST_API_KEY}

        response_zero = await admin_http_client.get("/api/v1/admin/costs?last=0", headers=headers)
        assert response_zero.status_code == 422

        response_over = await admin_http_client.get("/api/v1/admin/costs?last=101", headers=headers)
        assert response_over.status_code == 422

        response_ok = await admin_http_client.get("/api/v1/admin/costs?last=10", headers=headers)
        assert response_ok.status_code == 200
