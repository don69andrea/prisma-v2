"""Integration-Tests für GET /api/v1/stocks/{ticker}/langfrist-score."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.errors import YahooFinanceBlockedError
from backend.domain.value_objects.langfrist_score import LangfristScore
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_swiss_market_service

pytestmark = pytest.mark.integration

_NESN_SCORE = LangfristScore(
    ticker="NESN",
    value=8.2,
    components={"dividende": 8.5, "bilanz": 8.5, "stabilitaet": 8.0, "marktkapita": 10.0},
    explanation="Treiber: starke Dividendenrendite (>3%), Large-Cap (>10 Mrd. CHF).",
)


@pytest.fixture
def mock_swiss_service() -> Any:
    svc = AsyncMock(spec=SwissMarketService)

    async def _score_langfrist(ticker: str) -> LangfristScore:
        if ticker.upper() == "NESN":
            return _NESN_SCORE
        if ticker.upper() == "BLOCKED":
            raise YahooFinanceBlockedError(ticker.upper(), cause="401 Invalid Crumb")
        raise ValueError(f"Swiss Stock '{ticker.upper()}' nicht gefunden")

    svc.score_langfrist = _score_langfrist
    return svc


@pytest.fixture
def app(mock_swiss_service: Any) -> Any:
    application = create_app()
    application.dependency_overrides[get_swiss_market_service] = lambda: mock_swiss_service
    return application


@pytest.mark.asyncio
async def test_langfrist_score_nesn(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/NESN/langfrist-score")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NESN"
    assert data["value"] == pytest.approx(8.2)
    assert "dividende" in data["components"]
    assert "disclaimer" in data
    assert len(data["explanation"]) > 0


@pytest.mark.asyncio
async def test_langfrist_score_unknown_ticker(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/UNKN/langfrist-score")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_langfrist_score_yahoo_blocked_returns_503(app: Any) -> None:
    """Yahoo blockt Render's Cloud-IP-Range (HTTP 401 'Invalid Crumb') — muss als
    saubere 503 mit klarer Meldung ankommen, nicht als roher 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/BLOCKED/langfrist-score")
    assert resp.status_code == 503
    assert "nicht verfügbar" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_langfrist_score_case_insensitive(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/nesn/langfrist-score")
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "NESN"


@pytest.mark.asyncio
async def test_langfrist_score_components_schema(app: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stocks/NESN/langfrist-score")
    data = resp.json()
    for key in ("dividende", "bilanz", "stabilitaet", "marktkapita"):
        assert key in data["components"]
        assert 0.0 <= data["components"][key] <= 10.0
