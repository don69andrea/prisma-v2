"""Integration-Tests für POST /api/v1/steuer/einschaetzung."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.agents.steuer_agent import SteuerAgent
from backend.domain.schemas.steuer_schema import PFLICHT_DISCLAIMER, SteuerEinschätzung
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_steuer_agent

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 6, 8, 7, 0, tzinfo=UTC)

_SAMPLE_RESULT = SteuerEinschätzung(
    ticker="NESN",
    anlegerprofil="vorsorge_3a",
    halteperiode_jahre=30,
    steuerarten=["Verrechnungssteuer (35%)", "Vermögenssteuer"],
    pflichten=["VST-Rückerstattung via Formular 103"],
    hinweise=["3a-Erträge laufend steuerbefreit"],
    quellen=["ESTV VST"],
    disclaimer=PFLICHT_DISCLAIMER,
    generated_at=_NOW,
    model_version="claude-sonnet-4-6",
)


@pytest.fixture
def mock_steuer_agent() -> Any:
    svc = AsyncMock(spec=SteuerAgent)
    svc.einschaetzen.return_value = _SAMPLE_RESULT
    return svc


@pytest.fixture
def app(mock_steuer_agent: Any) -> Any:
    application = create_app()
    application.dependency_overrides[get_steuer_agent] = lambda: mock_steuer_agent
    return application


@pytest.mark.asyncio
async def test_steuer_einschaetzung_nesn(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/steuer/einschaetzung",
            json={"ticker": "NESN", "anlegerprofil": "vorsorge_3a", "halteperiode_jahre": 30},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["anlegerprofil"] == "vorsorge_3a"
    assert len(data["steuerarten"]) >= 1
    assert len(data["pflichten"]) >= 1
    assert "disclaimer" in data
    assert "Keine Steuerberatung" in data["disclaimer"] or "Steuerberatung" in data["disclaimer"]


@pytest.mark.asyncio
async def test_steuer_einschaetzung_default_profil(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/steuer/einschaetzung",
            json={"ticker": "NESN"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_steuer_einschaetzung_invalid_profil(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/steuer/einschaetzung",
            json={"ticker": "NESN", "anlegerprofil": "invalid_profile"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_steuer_einschaetzung_halteperiode_too_large(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/steuer/einschaetzung",
            json={"ticker": "NESN", "halteperiode_jahre": 51},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_steuer_agent_called_with_correct_args(app: Any, mock_steuer_agent: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/steuer/einschaetzung",
            json={"ticker": "ABBN", "anlegerprofil": "privatperson", "halteperiode_jahre": 10},
        )
    mock_steuer_agent.einschaetzen.assert_called_once_with(
        ticker="ABBN", anlegerprofil="privatperson", halteperiode_jahre=10
    )
