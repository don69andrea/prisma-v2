"""Integrationstests für GET /api/v1/signals und GET /api/v1/backtest/{coin}.

A7.9: Alle Endpoints geben valides Pydantic zurück (kein Freitext).

Teststrategie: Service-Layer wird gemockt — kein echter DB-Zugriff nötig.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.schemas.signals import BacktestReport, SignalVector

pytestmark = pytest.mark.integration

# ── Fixture-Daten ─────────────────────────────────────────────────────────────

_SIGNAL_BTC = SignalVector(
    coin="BTC-USD",
    asof=date(2025, 1, 15),
    action="BUY",
    size_factor=0.8,
    consensus="2/3",
    sub_scores={
        "ma_signal": 1.0,
        "macd_signal": 1.0,
        "rsi_signal": 0.0,
        "vol_pred": 0.55,
        "momentum_rank": 1.0,
        "onchain_score": 0.65,
    },
    confidence=0.67,
)

_SIGNAL_ETH = SignalVector(
    coin="ETH-USD",
    asof=date(2025, 1, 15),
    action="HOLD",
    size_factor=0.5,
    consensus="1/3",
    sub_scores={
        "ma_signal": 1.0,
        "macd_signal": 0.0,
        "rsi_signal": 0.0,
        "vol_pred": 0.70,
        "momentum_rank": 3.0,
        "onchain_score": 0.50,
    },
    confidence=0.33,
)

_BACKTEST_BTC = BacktestReport(
    coin="BTC-USD",
    cagr=0.42,
    sharpe=1.31,
    max_dd=-0.28,
    calmar=1.50,
    beats_exposure_matched=True,
    n_trades=24,
    equity_curve=[
        (date(2024, 1, 1), 1.00),
        (date(2024, 6, 30), 1.21),
        (date(2025, 1, 1), 1.42),
    ],
)


# ── Test-Client-Fixture ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as ac:
        yield ac


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signals_list_returns_list(client: AsyncClient) -> None:
    """GET /api/v1/signals → 200 mit list[SignalVector] (A7.9)."""
    with patch(
        "backend.interfaces.rest.routers.signals.signal_service.evaluate",
        new=AsyncMock(side_effect=[_SIGNAL_BTC, _SIGNAL_ETH]),
    ):
        response = await client.get("/api/v1/signals")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Valides Pydantic: kein Freitext, echte Felder
    first = data[0]
    assert "coin" in first
    assert "action" in first
    assert "size_factor" in first
    assert "consensus" in first
    assert "sub_scores" in first
    assert "confidence" in first


@pytest.mark.asyncio
async def test_signals_detail_returns_signalvector(client: AsyncClient) -> None:
    """GET /api/v1/signals/BTC-USD → 200, action ∈ {BUY, HOLD, SELL}, size_factor ∈ [0, 1.5] (A7.9)."""
    with patch(
        "backend.interfaces.rest.routers.signals.signal_service.evaluate",
        new=AsyncMock(return_value=_SIGNAL_BTC),
    ):
        response = await client.get("/api/v1/signals/BTC-USD")

    assert response.status_code == 200
    data = response.json()
    assert data["coin"] == "BTC-USD"
    assert data["action"] in ("BUY", "HOLD", "SELL")
    assert 0.0 <= data["size_factor"] <= 1.5
    assert isinstance(data["sub_scores"], dict)
    assert 0.0 <= data["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_signals_unknown_coin_404(client: AsyncClient) -> None:
    """GET /api/v1/signals/FAKE-USD → 404 wenn Coin nicht in crypto_universe."""
    response = await client.get("/api/v1/signals/FAKE-USD")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_backtest_returns_report(client: AsyncClient) -> None:
    """GET /api/v1/backtest/BTC-USD → 200, beats_exposure_matched ist bool (A7.9)."""
    with patch(
        "backend.interfaces.rest.routers.signals.run_walkforward",
        new=AsyncMock(return_value=_BACKTEST_BTC),
    ):
        response = await client.get("/api/v1/backtest/BTC-USD")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["coin"] == "BTC-USD"
    assert isinstance(data["beats_exposure_matched"], bool)
    assert "cagr" in data
    assert "sharpe" in data
    assert "max_dd" in data
    assert "calmar" in data
    assert "n_trades" in data
    assert "equity_curve" in data


@pytest.mark.asyncio
async def test_signalvector_schema_complete(client: AsyncClient) -> None:
    """Alle Pflichtfelder des SignalVector-Schemas sind im Response vorhanden (A7.9)."""
    with patch(
        "backend.interfaces.rest.routers.signals.signal_service.evaluate",
        new=AsyncMock(return_value=_SIGNAL_ETH),
    ):
        response = await client.get("/api/v1/signals/ETH-USD")

    assert response.status_code == 200
    data = response.json()

    required_fields = {"coin", "asof", "action", "size_factor", "consensus", "sub_scores", "confidence", "disclaimer"}
    assert required_fields <= set(data.keys()), (
        f"Fehlende Felder: {required_fields - set(data.keys())}"
    )
    # Typen prüfen
    assert isinstance(data["coin"], str)
    assert isinstance(data["asof"], str)  # ISO-date als String
    assert data["action"] in ("BUY", "HOLD", "SELL")
    assert isinstance(data["size_factor"], float | int)
    assert isinstance(data["consensus"], str)
    assert isinstance(data["sub_scores"], dict)
    assert isinstance(data["confidence"], float | int)
    assert isinstance(data["disclaimer"], str)


@pytest.mark.asyncio
async def test_backtest_unknown_coin_404(client: AsyncClient) -> None:
    """GET /api/v1/backtest/FAKE-USD → 404 wenn Coin unbekannt."""
    response = await client.get("/api/v1/backtest/FAKE-USD")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
