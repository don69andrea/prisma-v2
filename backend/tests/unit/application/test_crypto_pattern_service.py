"""Unit-Tests für CryptoPatternService — native Pattern-Erkennung (kein pandas-ta).

Scope: 7 Chart-Formationen (Golden/Death Cross, RSI-Extreme, MACD-Crossover,
EMA200, BB-Squeeze, Volumen-Breakout) + 2 mehrkerzige Candlestick-Muster
(Engulfing, Morning/Evening Star). Siehe docs/specs/2026-06-16-crypto-extension-plan.md.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pandas as pd

from backend.application.services.crypto_pattern_service import CryptoPatternService


def _flat_df(n: int = 250, price: float = 100.0, volume: float = 1_000_000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [price] * n,
            "High": [price * 1.001] * n,
            "Low": [price * 0.999] * n,
            "Close": [price] * n,
            "Volume": [volume] * n,
        }
    )


def _make_service(df: pd.DataFrame | None) -> CryptoPatternService:
    svc = CryptoPatternService()
    svc._adapter.get_ohlcv = AsyncMock(return_value=df)  # type: ignore[method-assign]
    return svc


class TestDetectGuardClauses:
    async def test_none_dataframe_returns_empty(self) -> None:
        svc = _make_service(None)
        patterns, modifier = await svc.detect("BTC-CHF")
        assert patterns == []
        assert modifier == 0.0

    async def test_too_short_dataframe_returns_empty(self) -> None:
        svc = _make_service(_flat_df(5))
        patterns, modifier = await svc.detect("BTC-CHF")
        assert patterns == []
        assert modifier == 0.0

    async def test_modifier_always_within_bounds(self) -> None:
        svc = _make_service(_flat_df(250))
        _, modifier = await svc.detect("BTC-CHF")
        assert -7.5 <= modifier <= 7.5

    async def test_max_10_patterns_returned(self) -> None:
        svc = _make_service(_flat_df(250))
        patterns, _ = await svc.detect("BTC-CHF")
        assert len(patterns) <= 10


class TestChartFormations:
    async def test_golden_cross_detected_on_ema_crossover(self) -> None:
        # Preis fällt zunächst (ema20 < ema50), dreht dann scharf nach oben,
        # sodass ema20 ema50 am letzten Tag von unten nach oben kreuzt.
        n = 66
        prices = [200.0 - i for i in range(60)] + [140.0 + i * (110.0 / 6) for i in range(6)]
        df = pd.DataFrame(
            {
                "Open": prices,
                "High": [p * 1.01 for p in prices],
                "Low": [p * 0.99 for p in prices],
                "Close": prices,
                "Volume": [1_000_000.0] * n,
            }
        )
        svc = _make_service(df)
        patterns, modifier = await svc.detect("BTC-CHF")
        assert "GOLDEN_CROSS" in patterns
        assert modifier > 0.0

    async def test_rsi_oversold_on_sustained_downtrend(self) -> None:
        n = 60
        prices = [100.0 - i * 1.2 for i in range(n)]
        df = pd.DataFrame(
            {
                "Open": prices,
                "High": prices,
                "Low": prices,
                "Close": prices,
                "Volume": [1_000_000.0] * n,
            }
        )
        svc = _make_service(df)
        patterns, _ = await svc.detect("ETH-USD")
        assert "RSI_OVERSOLD" in patterns

    async def test_volume_breakout_on_volume_spike(self) -> None:
        n = 30
        prices = [100.0] * n
        volume = [1_000_000.0] * (n - 1) + [3_000_000.0]
        df = pd.DataFrame(
            {"Open": prices, "High": prices, "Low": prices, "Close": prices, "Volume": volume}
        )
        svc = _make_service(df)
        patterns, _ = await svc.detect("SOL-USD")
        assert "VOL_BREAKOUT" in patterns

    async def test_bb_squeeze_on_flat_prices(self) -> None:
        svc = _make_service(_flat_df(60))
        patterns, _ = await svc.detect("ADA-USD")
        assert "BB_SQUEEZE" in patterns


class TestCandlestickPatterns:
    async def test_bullish_engulfing_detected(self) -> None:
        n = 30
        base = [100.0] * (n - 2)
        df = pd.DataFrame(
            {
                "Open": base + [102.0, 96.0],
                "High": base + [102.5, 103.5],
                "Low": base + [99.5, 95.5],
                "Close": base + [100.0, 103.0],
                "Volume": [1_000_000.0] * n,
            }
        )
        svc = _make_service(df)
        patterns, modifier = await svc.detect("BTC-CHF")
        assert "BULLISH_ENGULFING" in patterns
        assert modifier > 0.0

    async def test_bearish_engulfing_detected(self) -> None:
        n = 30
        base = [100.0] * (n - 2)
        df = pd.DataFrame(
            {
                "Open": base + [98.0, 104.0],
                "High": base + [100.5, 104.5],
                "Low": base + [97.5, 96.5],
                "Close": base + [100.0, 97.0],
                "Volume": [1_000_000.0] * n,
            }
        )
        svc = _make_service(df)
        patterns, modifier = await svc.detect("BTC-CHF")
        assert "BEARISH_ENGULFING" in patterns
        assert modifier < 0.0
