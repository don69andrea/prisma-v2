"""Unit-Tests für CryptoScoringService — BUG-04 + PERF-03 Regression."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from backend.application.services.crypto_scoring_service import CryptoScoringService

pytestmark = pytest.mark.unit


def _make_minimal_df() -> pd.DataFrame:
    """Minimaler DataFrame mit allen von CryptoScorer benötigten Spalten."""
    n = 60
    base = 50_000.0
    prices = [base + i * 10 for i in range(n)]
    return pd.DataFrame(
        {
            "Close": prices,
            "Open": prices,
            "High": [p * 1.001 for p in prices],
            "Low": [p * 0.999 for p in prices],
            "Volume": [1_000_000.0] * n,
            "RSI_14": [55.0] * n,
            "MACD_12_26_9": [100.0] * n,
            "MACDs_12_26_9": [80.0] * n,
            "MACDh_12_26_9": [20.0] * n,
            "EMA_20": [p * 0.998 for p in prices],
            "EMA_50": [p * 0.995 for p in prices],
            "BBU_20_2.0": [p * 1.02 for p in prices],
            "BBL_20_2.0": [p * 0.98 for p in prices],
        }
    )


def _make_service(tech_df: pd.DataFrame | None = None) -> CryptoScoringService:
    cg = AsyncMock()
    cg.get_market_data = AsyncMock(
        return_value=[
            {
                "id": "bitcoin",
                "current_price": 90_000.0,
                "market_cap": 1_800_000_000_000,
                "total_volume": 30_000_000_000,
                "price_change_percentage_24h": 1.5,
                "price_change_percentage_7d_in_currency": 3.2,
                "ath_change_percentage": -5.0,
                "market_cap_rank": 1,
            }
        ]
    )
    yf = AsyncMock()
    yf.get_technicals = AsyncMock(
        return_value=tech_df if tech_df is not None else _make_minimal_df()
    )
    yf.get_smi_correlation = AsyncMock(return_value=0.25)

    fg = AsyncMock()
    fg.get_current = AsyncMock(return_value={"value": 42, "label": "Fear"})

    pattern = AsyncMock()
    pattern.detect = AsyncMock(return_value=(["GOLDEN_CROSS"], 2.5))

    from backend.domain.services.crypto_scorer import CryptoScorer

    return CryptoScoringService(
        cg_adapter=cg,
        yf_adapter=yf,
        fg_adapter=fg,
        scorer=CryptoScorer(),
        pattern_service=pattern,
    )


# ---------------------------------------------------------------------------
# BUG-04: score_one() darf score_all() NICHT aufrufen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_one_does_not_call_score_all() -> None:
    """BUG-04: score_one() rief früher score_all() auf → 30+ HTTP-Calls für 1 Ticker.
    Nach dem Fix muss score_all() bei score_one() NICHT aufgerufen werden."""
    svc = _make_service()

    with patch.object(svc, "score_all", wraps=svc.score_all) as mock_score_all:
        await svc.score_one("BTC")

    mock_score_all.assert_not_called()


@pytest.mark.asyncio
async def test_score_one_returns_correct_ticker() -> None:
    """score_one('BTC') gibt das Signal für BTC zurück."""
    svc = _make_service()
    result = await svc.score_one("BTC")
    assert result is not None
    assert result.ticker == "BTC"


@pytest.mark.asyncio
async def test_score_one_returns_none_for_unknown_ticker() -> None:
    """score_one() gibt None für nicht unterstützte Ticker zurück."""
    svc = _make_service()
    result = await svc.score_one("DOGE9999")
    assert result is None


@pytest.mark.asyncio
async def test_score_one_makes_fewer_api_calls_than_score_all() -> None:
    """BUG-04 Beweis: score_one() soll NUR die Daten für EINEN Ticker abrufen.
    score_all() lädt 10 Kryptos → 10x yfinance. score_one() darf max. 2x rufen."""
    svc = _make_service()
    yf_mock = cast(Any, svc._yf)

    yf_mock.get_technicals.reset_mock()
    await svc.score_one("BTC")
    one_ticker_calls = yf_mock.get_technicals.call_count

    yf_mock.get_technicals.reset_mock()
    await svc.score_all()
    all_ticker_calls = yf_mock.get_technicals.call_count

    assert one_ticker_calls < all_ticker_calls, (
        f"score_one() macht {one_ticker_calls} yfinance-Calls, "
        f"score_all() macht {all_ticker_calls} — score_one() muss weniger sein."
    )


# ---------------------------------------------------------------------------
# PERF-03: Request-Level-Cache verhindert parallele Stampede
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_score_all_calls_only_fetch_once() -> None:
    """PERF-03: Gleichzeitige Requests sollen nur einen score_all()-Durchlauf auslösen.
    Ohne Cache würden N parallele Requests N×30 yfinance-Calls machen."""
    svc = _make_service()
    call_count = 0
    original_get_market = svc._cg.get_market_data

    async def _tracked_market(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_get_market(*args, **kwargs)

    cast(Any, svc._cg).get_market_data = _tracked_market

    # 3 gleichzeitige Requests
    results = await asyncio.gather(svc.score_all(), svc.score_all(), svc.score_all())

    assert all(len(r) > 0 for r in results), "Alle 3 Calls müssen Ergebnisse liefern"
    assert call_count == 1, (
        f"CoinGecko wurde {call_count}× aufgerufen — erwartet 1 (Cache aktiv). "
        "PERF-03: asyncio.Lock + Memo-Cache muss parallele Stampede verhindern."
    )


@pytest.mark.asyncio
async def test_score_all_cache_expires() -> None:
    """PERF-03: Nach Ablauf des Cache-TTL soll ein neuer API-Call gemacht werden."""
    svc = _make_service()
    original = svc._cg.get_market_data
    call_count = 0

    async def _counted(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original(*args, **kwargs)

    cast(Any, svc._cg).get_market_data = _counted

    await svc.score_all()
    assert call_count == 1

    # Cache leeren (simuliert Ablauf)
    cast(Any, svc)._cache_result = None

    await svc.score_all()
    assert call_count == 2, "Nach Cache-Ablauf muss ein neuer API-Call gemacht werden."
