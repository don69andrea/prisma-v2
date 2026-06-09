"""Integrationstests für GET + POST /api/v1/decisions/{ticker}/audit."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.decision_audit_service import DecisionAuditService
from backend.domain.entities.decision_audit_record import DecisionAuditRecord
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.routers.decision_audit import get_audit_service

pytestmark = pytest.mark.integration

_RECORD = DecisionAuditRecord(
    id=uuid4(),
    ticker="NESN",
    signal="BUY",
    weighted_score=72.5,
    quant_score=75.0,
    ml_score=68.0,
    macro_score=65.0,
    is_3a_eligible=True,
    snapshot_date=date(2026, 6, 9),
    computed_at=datetime.now(tz=UTC),
    explanation_de="Starke Fundamentaldaten, positives Makroklima.",
)


def _mock_audit_service() -> DecisionAuditService:
    svc = MagicMock(spec=DecisionAuditService)
    svc.get_audit_trail = AsyncMock(return_value=[_RECORD])
    svc.compute_and_save = AsyncMock(return_value=_RECORD)
    return svc


@pytest.fixture
def app() -> Any:
    application = create_app()
    application.dependency_overrides[get_audit_service] = _mock_audit_service
    return application


@pytest.mark.asyncio
async def test_get_audit_trail_returns_200(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/decisions/NESN/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert len(data["records"]) == 1
    assert data["records"][0]["signal"] == "BUY"


@pytest.mark.asyncio
async def test_get_audit_trail_record_fields(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/decisions/NESN/audit")
    record = resp.json()["records"][0]
    for field in ("weighted_score", "quant_score", "ml_score", "macro_score", "explanation_de"):
        assert field in record


@pytest.mark.asyncio
async def test_post_audit_computes_and_returns_record(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/decisions/NESN/audit")
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["signal"] in ("BUY", "HOLD", "WATCH")
