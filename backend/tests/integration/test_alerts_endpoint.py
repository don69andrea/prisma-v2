"""Integrationstests für POST/GET/DELETE /api/v1/alerts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.alert_service import AlertService
from backend.domain.entities.alert import Alert
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.routers.alerts import _get_alert_service

pytestmark = pytest.mark.integration

_ALERT_ID = uuid4()
_ALERT = Alert(
    id=_ALERT_ID,
    ticker="NESN",
    trigger_type="PRICE_CHANGE",
    threshold=5.0,
    channel="EMAIL",
    target="test@example.com",
    is_active=True,
    created_at=datetime.now(tz=UTC),
    last_triggered_at=None,
    last_signal=None,
    baseline_price=100.0,
)


def _mock_alert_service() -> AlertService:
    svc = MagicMock(spec=AlertService)
    svc.create_alert = AsyncMock(return_value=_ALERT)
    svc.list_alerts = AsyncMock(return_value=[_ALERT])
    svc.delete_alert = AsyncMock(return_value=True)
    return svc


@pytest.fixture
def app() -> Any:
    application = create_app()
    application.dependency_overrides[_get_alert_service] = _mock_alert_service
    return application


@pytest.mark.asyncio
async def test_create_alert_returns_201(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/alerts",
            json={
                "ticker": "NESN",
                "trigger_type": "PRICE_CHANGE",
                "threshold": 5.0,
                "channel": "EMAIL",
                "target": "test@example.com",
            },
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["trigger_type"] == "PRICE_CHANGE"


@pytest.mark.asyncio
async def test_list_alerts_returns_200(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "alerts" in data
    assert len(data["alerts"]) == 1


@pytest.mark.asyncio
async def test_delete_alert_returns_204(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/alerts/{_ALERT_ID}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_alert_invalid_channel_returns_422(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/alerts",
            json={
                "ticker": "NESN",
                "trigger_type": "PRICE_CHANGE",
                "threshold": 5.0,
                "channel": "TELEGRAM",
                "target": "test@example.com",
            },
        )
    assert resp.status_code == 422
