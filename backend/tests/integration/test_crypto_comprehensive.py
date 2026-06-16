"""Umfassende Integrationstests für /api/v1/crypto/* — HTTP-Schicht, Schema, Sortierung, Bounds.

Alle externen APIs (CoinGecko, Fear&Greed, yFinance) sind gemockt.
Kein Datenbankzugriff erforderlich.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.domain.value_objects.crypto_signal import CryptoSignal

pytestmark = pytest.mark.asyncio

_VALID_SIGNALS = {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"}
_VALID_MACD = {"bullish", "bearish"}

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _make_signal(
    ticker: str = "BTC",
    score: float = 65.0,
    signal: str = "BUY",
) -> CryptoSignal:
    return CryptoSignal(
        ticker=ticker,
        name={"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana"}.get(ticker, ticker),
        signal=signal,  # type: ignore[arg-type]
        score=score,
        score_components={
            "momentum": score * 0.30,
            "trend": score * 0.25,
            "sentiment": score * 0.20,
            "markt": score * 0.15,
            "risiko": score * 0.10,
        },
        signal_reason_de=f"Test-Signal für {ticker}.",
        fear_greed_value=35,
        fear_greed_label="Fear",
        rsi_14=42.0,
        macd_signal="bullish",
        volatility_30d_pct=45.0,
        correlation_smi_1y=0.15,
        has_six_etp=ticker in ("BTC", "ETH"),
        price_chf=50000.0 if ticker == "BTC" else 3000.0,
        market_cap_chf=1e12,
        price_change_24h_pct=1.5,
        price_change_7d_pct=5.0,
        ath_change_pct=-30.0,
        market_cap_rank=1 if ticker == "BTC" else 2,
        timestamp=datetime.now(tz=UTC),
    )


def _make_ten_signals() -> list[CryptoSignal]:
    """Erstellt 10 Signale in absteigender Score-Reihenfolge."""
    tickers_and_scores = [
        ("BTC", 82.0, "STRONG_BUY"),
        ("ETH", 71.0, "BUY"),
        ("SOL", 65.0, "BUY"),
        ("BNB", 58.0, "HOLD"),
        ("XRP", 52.0, "HOLD"),
        ("ADA", 48.0, "HOLD"),
        ("DOT", 43.0, "HOLD"),
        ("MATIC", 35.0, "SELL"),
        ("LINK", 28.0, "SELL"),
        ("AVAX", 18.0, "STRONG_SELL"),
    ]
    return [_make_signal(t, s, sig) for t, s, sig in tickers_and_scores]


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    signals = _make_ten_signals()
    svc.score_all.return_value = signals
    svc.score_one.return_value = signals[0]
    return svc


@pytest.fixture
async def client(mock_service):
    from backend.interfaces.rest.app import create_app
    from backend.interfaces.rest.dependencies import get_crypto_scoring_service

    app = create_app()
    app.dependency_overrides[get_crypto_scoring_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


_HEADERS = {"X-API-Key": "test"}
_FEAR_GREED_PATCH = patch(
    "backend.infrastructure.adapters.fear_greed_adapter.FearGreedAdapter.get_current",
    new_callable=AsyncMock,
    return_value={"value": 35, "label": "Fear", "timestamp": "1700000000"},
)
_MARKET_PATCH = patch(
    "backend.infrastructure.adapters.coingecko_adapter.CoinGeckoAdapter.get_market_data",
    new_callable=AsyncMock,
    return_value=[{"id": "bitcoin", "current_price": 50000}],
)


# ── /api/v1/crypto/signals ────────────────────────────────────────────────────


class TestSignalsEndpoint:
    async def test_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        assert r.status_code == 200

    async def test_returns_list(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        assert isinstance(r.json(), list)

    async def test_returns_ten_signals(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        assert len(r.json()) == 10

    async def test_required_fields_present(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        item = r.json()[0]
        for field in (
            "ticker",
            "name",
            "signal",
            "score",
            "score_components",
            "signal_reason_de",
            "fear_greed_value",
            "fear_greed_label",
            "rsi_14",
            "macd_signal",
            "volatility_30d_pct",
            "correlation_smi_1y",
            "has_six_etp",
            "timestamp",
        ):
            assert field in item, f"Fehlendes Feld: {field}"

    async def test_score_in_valid_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert 0 <= item["score"] <= 100, f"Score {item['score']} ausserhalb [0,100]"

    async def test_signal_in_valid_enum(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert item["signal"] in _VALID_SIGNALS, f"Ungültiges Signal: {item['signal']}"

    async def test_score_components_has_five_keys(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            comp = item["score_components"]
            for key in ("momentum", "trend", "sentiment", "markt", "risiko"):
                assert key in comp, f"Fehlende Komponente: {key}"

    async def test_score_components_are_non_negative(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            for key, val in item["score_components"].items():
                assert val >= 0, f"{key}={val} ist negativ"

    async def test_sorted_by_score_descending(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        scores = [item["score"] for item in r.json()]
        assert scores == sorted(scores, reverse=True), (
            "Signale sind nicht absteigend nach Score sortiert"
        )

    async def test_macd_signal_in_valid_values(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert item["macd_signal"] in _VALID_MACD

    async def test_fear_greed_value_in_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert 0 <= item["fear_greed_value"] <= 100

    async def test_rsi_14_in_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert 0 <= item["rsi_14"] <= 100

    async def test_has_six_etp_is_boolean(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert isinstance(item["has_six_etp"], bool)

    async def test_ticker_is_nonempty_string(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert isinstance(item["ticker"], str) and len(item["ticker"]) > 0

    async def test_price_chf_nullable(self, client: AsyncClient) -> None:
        """price_chf darf None (null) oder float sein."""
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        for item in r.json():
            assert item["price_chf"] is None or isinstance(item["price_chf"], (int, float))

    async def test_no_api_key_still_returns_200(self, client: AsyncClient) -> None:
        """Crypto-Endpoints erfordern keinen API-Key — öffentlich zugänglich."""
        r = await client.get("/api/v1/crypto/signals")
        assert r.status_code == 200

    async def test_six_etp_true_for_btc(self, client: AsyncClient) -> None:
        """BTC hat SIX ETP — has_six_etp muss True sein."""
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        btc = next(item for item in r.json() if item["ticker"] == "BTC")
        assert btc["has_six_etp"] is True

    async def test_strong_buy_has_highest_score(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        items = r.json()
        strong_buys = [x for x in items if x["signal"] == "STRONG_BUY"]
        buys = [x for x in items if x["signal"] == "BUY"]
        if strong_buys and buys:
            assert min(x["score"] for x in strong_buys) >= min(x["score"] for x in buys)


# ── /api/v1/crypto/signals/{ticker} ──────────────────────────────────────────


class TestSignalByTickerEndpoint:
    async def test_known_ticker_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals/BTC", headers=_HEADERS)
        assert r.status_code == 200

    async def test_response_ticker_matches_request(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals/BTC", headers=_HEADERS)
        assert r.json()["ticker"] == "BTC"

    async def test_unknown_ticker_returns_404(
        self, client: AsyncClient, mock_service: AsyncMock
    ) -> None:
        mock_service.score_one.return_value = None
        r = await client.get("/api/v1/crypto/signals/UNKNOWN", headers=_HEADERS)
        assert r.status_code == 404

    async def test_single_signal_has_all_fields(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals/BTC", headers=_HEADERS)
        item = r.json()
        for field in ("ticker", "signal", "score", "score_components", "has_six_etp"):
            assert field in item

    async def test_no_api_key_still_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals/BTC")
        assert r.status_code == 200

    async def test_signal_reason_is_nonempty_string(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/crypto/signals/BTC", headers=_HEADERS)
        reason = r.json().get("signal_reason_de", "")
        assert isinstance(reason, str) and len(reason) > 0


# ── /api/v1/crypto/fear-greed ────────────────────────────────────────────────


class TestFearGreedEndpoint:
    async def test_returns_200(self, client: AsyncClient) -> None:
        with _FEAR_GREED_PATCH:
            r = await client.get("/api/v1/crypto/fear-greed", headers=_HEADERS)
        assert r.status_code == 200

    async def test_has_value_and_label(self, client: AsyncClient) -> None:
        with _FEAR_GREED_PATCH:
            r = await client.get("/api/v1/crypto/fear-greed", headers=_HEADERS)
        body = r.json()
        assert "value" in body
        assert "label" in body
        assert "timestamp" in body

    async def test_value_is_integer(self, client: AsyncClient) -> None:
        with _FEAR_GREED_PATCH:
            r = await client.get("/api/v1/crypto/fear-greed", headers=_HEADERS)
        value = r.json()["value"]
        assert isinstance(value, int)

    async def test_value_in_valid_range(self, client: AsyncClient) -> None:
        with _FEAR_GREED_PATCH:
            r = await client.get("/api/v1/crypto/fear-greed", headers=_HEADERS)
        assert 0 <= r.json()["value"] <= 100

    async def test_no_api_key_still_returns_200(self, client: AsyncClient) -> None:
        with _FEAR_GREED_PATCH:
            r = await client.get("/api/v1/crypto/fear-greed")
        assert r.status_code == 200


# ── /api/v1/crypto/market ────────────────────────────────────────────────────


class TestMarketEndpoint:
    async def test_returns_200(self, client: AsyncClient) -> None:
        with _MARKET_PATCH:
            r = await client.get("/api/v1/crypto/market", headers=_HEADERS)
        assert r.status_code == 200

    async def test_returns_list(self, client: AsyncClient) -> None:
        with _MARKET_PATCH:
            r = await client.get("/api/v1/crypto/market", headers=_HEADERS)
        assert isinstance(r.json(), list)

    async def test_no_api_key_still_returns_200(self, client: AsyncClient) -> None:
        with _MARKET_PATCH:
            r = await client.get("/api/v1/crypto/market")
        assert r.status_code == 200


# ── Fehlerfortpflanzung ───────────────────────────────────────────────────────


class TestErrorPropagation:
    async def test_service_exception_returns_500(
        self, client: AsyncClient, mock_service: AsyncMock
    ) -> None:
        mock_service.score_all.side_effect = RuntimeError("Datenbankfehler")
        r = await client.get("/api/v1/crypto/signals", headers=_HEADERS)
        assert r.status_code == 500

    async def test_service_exception_single_returns_500(
        self, client: AsyncClient, mock_service: AsyncMock
    ) -> None:
        mock_service.score_one.side_effect = RuntimeError("Timeout")
        r = await client.get("/api/v1/crypto/signals/BTC", headers=_HEADERS)
        assert r.status_code == 500
