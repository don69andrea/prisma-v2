"""Integrationstests für /api/v1/crypto/* — HTTP-Schicht ohne externe APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.domain.value_objects.crypto_signal import CryptoSignal

pytestmark = pytest.mark.asyncio


def _make_signal(ticker: str = "BTC", score: float = 65.0) -> CryptoSignal:
    return CryptoSignal(
        ticker=ticker,
        name="Bitcoin" if ticker == "BTC" else ticker,
        signal="BUY",
        score=score,
        score_components={
            "momentum": 20.0,
            "trend": 18.0,
            "sentiment": 14.0,
            "markt": 8.0,
            "risiko": 5.0,
        },
        signal_reason_de="Test-Signal.",
        fear_greed_value=35,
        fear_greed_label="Fear",
        rsi_14=42.0,
        macd_signal="bullish",
        volatility_30d_pct=45.0,
        correlation_smi_1y=0.15,
        has_six_etp=True,
        price_chf=50000.0,
        market_cap_chf=1e12,
        price_change_24h_pct=1.5,
        price_change_7d_pct=5.0,
        ath_change_pct=-30.0,
        market_cap_rank=1,
        timestamp=datetime.now(tz=UTC),
    )


@pytest.fixture
def mock_crypto_service():
    service = AsyncMock()
    service.score_all.return_value = [_make_signal("BTC", 65.0), _make_signal("ETH", 58.0)]
    service.score_one.return_value = _make_signal("BTC", 65.0)
    return service


@pytest.fixture
async def crypto_client(mock_crypto_service):
    from backend.interfaces.rest.app import create_app
    from backend.interfaces.rest.dependencies import get_crypto_scoring_service

    app = create_app()
    app.dependency_overrides[get_crypto_scoring_service] = lambda: mock_crypto_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_get_signals_returns_200(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals", headers={"X-API-Key": "test"})
    assert response.status_code == 200


async def test_get_signals_returns_list(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals", headers={"X-API-Key": "test"})
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2


async def test_get_signals_has_required_fields(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals", headers={"X-API-Key": "test"})
    first = response.json()[0]
    for field in [
        "ticker",
        "signal",
        "score",
        "score_components",
        "rsi_14",
        "fear_greed_value",
        "has_six_etp",
    ]:
        assert field in first, f"Missing field: {field}"


async def test_get_signal_by_ticker_returns_200(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals/BTC", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    assert response.json()["ticker"] == "BTC"


async def test_get_signal_invalid_ticker_returns_404(
    crypto_client: AsyncClient, mock_crypto_service: AsyncMock
) -> None:
    mock_crypto_service.score_one.return_value = None
    response = await crypto_client.get(
        "/api/v1/crypto/signals/UNKNOWN", headers={"X-API-Key": "test"}
    )
    assert response.status_code == 404


async def test_get_fear_greed_returns_200(crypto_client: AsyncClient) -> None:
    with patch(
        "backend.infrastructure.adapters.fear_greed_adapter.FearGreedAdapter.get_current",
        new_callable=AsyncMock,
        return_value={"value": 35, "label": "Fear", "timestamp": "1234567890"},
    ):
        response = await crypto_client.get(
            "/api/v1/crypto/fear-greed", headers={"X-API-Key": "test"}
        )
    assert response.status_code == 200
    body = response.json()
    assert "value" in body
    assert "label" in body


async def test_get_market_returns_200(crypto_client: AsyncClient) -> None:
    with patch(
        "backend.infrastructure.adapters.coingecko_adapter.CoinGeckoAdapter.get_market_data",
        new_callable=AsyncMock,
        return_value=[{"id": "bitcoin", "current_price": 50000}],
    ):
        response = await crypto_client.get("/api/v1/crypto/market", headers={"X-API-Key": "test"})
    assert response.status_code == 200


# ─────────────────────────── History-Endpoints (EXT-1) ───────────────────────────


@pytest.fixture
def mock_crypto_signal_repo():
    from backend.domain.models.crypto_signal_record import CryptoSignalRecord

    repo = AsyncMock()
    repo.get_history.return_value = [
        CryptoSignalRecord(
            ticker="BTC",
            signal="BUY",
            score=72.0,
            rsi_14=42.0,
            detected_patterns=["GOLDEN_CROSS"],
            pattern_score=2.5,
        )
    ]
    repo.get_latest_all.return_value = [
        CryptoSignalRecord(ticker="BTC", signal="BUY", score=72.0),
        CryptoSignalRecord(ticker="ETH", signal="HOLD", score=55.0),
    ]
    return repo


@pytest.fixture
async def crypto_history_client(mock_crypto_signal_repo):
    from backend.interfaces.rest.app import create_app
    from backend.interfaces.rest.dependencies import get_crypto_signal_repository

    app = create_app()
    app.dependency_overrides[get_crypto_signal_repository] = lambda: mock_crypto_signal_repo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_get_history_for_ticker_returns_200(crypto_history_client: AsyncClient) -> None:
    response = await crypto_history_client.get(
        "/api/v1/crypto/history/BTC", headers={"X-API-Key": "test"}
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["signal"] == "BUY"
    assert body[0]["detected_patterns"] == ["GOLDEN_CROSS"]


async def test_get_latest_history_overview_returns_200(crypto_history_client: AsyncClient) -> None:
    response = await crypto_history_client.get(
        "/api/v1/crypto/history", headers={"X-API-Key": "test"}
    )
    assert response.status_code == 200
    body = response.json()
    tickers = {item["ticker"] for item in body}
    assert tickers == {"BTC", "ETH"}
