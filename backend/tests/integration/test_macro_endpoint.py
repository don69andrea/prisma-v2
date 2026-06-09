"""Integrationstests für GET /api/v1/macro/context."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.macro_service import MacroService
from backend.domain.value_objects.macro_context import MacroContext
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.routers.macro import get_macro_service

pytestmark = pytest.mark.integration

_MOCK_CONTEXT = MacroContext(
    leitzins=0.25,
    chf_eur=0.93,
    inflation_ch=1.1,
    pmi_ch=52.3,
    snapshot_date=date(2026, 6, 9),
    climate="NEUTRAL",
    narrative_de="Stabiles makroökonomisches Umfeld.",
    narrative_en="Stable macroeconomic environment.",
)


def _mock_macro_service() -> MacroService:
    svc = MagicMock(spec=MacroService)
    svc.get_context = AsyncMock(return_value=_MOCK_CONTEXT)
    return svc


@pytest.fixture
def app() -> Any:
    application = create_app()
    application.dependency_overrides[get_macro_service] = _mock_macro_service
    return application


@pytest.mark.asyncio
async def test_macro_context_returns_200(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/macro/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["leitzins"] == pytest.approx(0.25)
    assert data["climate"] == "NEUTRAL"


@pytest.mark.asyncio
async def test_macro_context_includes_narratives(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/macro/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "narrative_de" in data
    assert "narrative_en" in data
    assert len(data["narrative_de"]) > 0


@pytest.mark.asyncio
async def test_macro_context_service_error_returns_503(app: Any) -> None:
    broken_svc = MagicMock(spec=MacroService)
    broken_svc.get_context = AsyncMock(side_effect=RuntimeError("SNB unreachable"))

    application = create_app()
    application.dependency_overrides[get_macro_service] = lambda: broken_svc

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/macro/context")
    assert resp.status_code == 503
