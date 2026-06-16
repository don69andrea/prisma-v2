"""CryptoPatternService — erkennt Chart-Formationen + Candlestick-Muster.

Bewusst nativ mit pandas/numpy implementiert: `pandas-ta` wurde am 2026-06-16
(Commit 53aaa658) aus dem Projekt entfernt, weil es über numba/llvmlite
~500MB zusätzliche Abhängigkeiten zog und auf Render Free Tier zu
OOM-Crashes führte. Siehe docs/specs/2026-06-16-crypto-extension-plan.md.

Scope bewusst auf robuste, mehrkerzig bestätigte Muster beschränkt:
Einzelkerzen-Muster (Doji, Hammer, Shooting Star etc.) haben in 24/7
Krypto-Märkten eine schwache eigenständige Trefferquote.
"""

from __future__ import annotations

import pandas as pd

from backend.infrastructure.adapters.yfinance_crypto import (
    YFinanceCryptoAdapter,
    _bbands,
    _ema,
    _macd,
    _rsi,
)

# Gewichtung pro erkanntem Pattern (bullish positiv, bearish negativ).
# Summe wird auf [-7.5, +7.5] geclampt und additiv auf den 0-100 CryptoScore angewendet.
PATTERN_WEIGHTS: dict[str, float] = {
    "GOLDEN_CROSS": 2.5,
    "DEATH_CROSS": -2.5,
    "RSI_OVERSOLD": 1.5,
    "RSI_OVERBOUGHT": -1.5,
    "MACD_BULLISH": 1.5,
    "MACD_BEARISH": -1.5,
    "PRICE_ABOVE_EMA200": 1.0,
    "PRICE_BELOW_EMA200": -1.0,
    "BB_SQUEEZE": 0.5,
    "VOL_BREAKOUT": 1.5,
    "BULLISH_ENGULFING": 2.0,
    "BEARISH_ENGULFING": -2.0,
    "MORNING_STAR": 2.5,
    "EVENING_STAR": -2.5,
}

_MODIFIER_CAP = 7.5
_MIN_BARS = 10


class CryptoPatternService:
    """Erkennt Chart-Formationen + 2 Candlestick-Muster aus OHLCV-Daten."""

    def __init__(self) -> None:
        self._adapter = YFinanceCryptoAdapter()

    async def detect(self, ticker_yf: str) -> tuple[list[str], float]:
        """Gibt (erkannte_pattern_namen, pattern_modifier) zurück.

        `pattern_modifier` liegt immer in [-7.5, +7.5] und wird vom Aufrufer
        additiv auf den bestehenden 0-100 CryptoScore angewendet (kein
        eigenes hartes Dimension-Cap, um bestehende Signal-Schwellen nicht
        zu verschieben).
        """
        df = await self._adapter.get_ohlcv(ticker_yf)
        if df is None or len(df) < _MIN_BARS:
            return [], 0.0

        patterns: list[str] = []
        raw = 0.0

        chart_patterns, chart_raw = self._detect_chart_patterns(df)
        patterns.extend(chart_patterns)
        raw += chart_raw

        candle_patterns, candle_raw = self._detect_candlestick_patterns(df)
        patterns.extend(candle_patterns)
        raw += candle_raw

        modifier = max(-_MODIFIER_CAP, min(_MODIFIER_CAP, raw))
        return patterns[:10], round(modifier, 1)

    def _detect_chart_patterns(self, df: pd.DataFrame) -> tuple[list[str], float]:
        patterns: list[str] = []
        score = 0.0
        close, volume = df["Close"], df["Volume"]

        ema20, ema50, ema200 = _ema(close, 20), _ema(close, 50), _ema(close, 200)
        rsi = _rsi(close, 14)
        macd_line, signal_line, _hist = _macd(close)
        upper, _mid, lower = _bbands(close)

        last_close = float(close.iloc[-1])

        if len(ema20) > 1 and len(ema50) > 1:
            if ema20.iloc[-1] > ema50.iloc[-1] and ema20.iloc[-2] <= ema50.iloc[-2]:
                patterns.append("GOLDEN_CROSS")
                score += PATTERN_WEIGHTS["GOLDEN_CROSS"]
            elif ema20.iloc[-1] < ema50.iloc[-1] and ema20.iloc[-2] >= ema50.iloc[-2]:
                patterns.append("DEATH_CROSS")
                score += PATTERN_WEIGHTS["DEATH_CROSS"]

        if not rsi.dropna().empty:
            last_rsi = rsi.iloc[-1]
            if last_rsi < 30:
                patterns.append("RSI_OVERSOLD")
                score += PATTERN_WEIGHTS["RSI_OVERSOLD"]
            elif last_rsi > 70:
                patterns.append("RSI_OVERBOUGHT")
                score += PATTERN_WEIGHTS["RSI_OVERBOUGHT"]

        if len(macd_line) > 1 and len(signal_line) > 1:
            if (
                macd_line.iloc[-1] > signal_line.iloc[-1]
                and macd_line.iloc[-2] <= signal_line.iloc[-2]
            ):
                patterns.append("MACD_BULLISH")
                score += PATTERN_WEIGHTS["MACD_BULLISH"]
            elif (
                macd_line.iloc[-1] < signal_line.iloc[-1]
                and macd_line.iloc[-2] >= signal_line.iloc[-2]
            ):
                patterns.append("MACD_BEARISH")
                score += PATTERN_WEIGHTS["MACD_BEARISH"]

        if not ema200.dropna().empty:
            e200 = ema200.iloc[-1]
            if last_close > e200:
                patterns.append("PRICE_ABOVE_EMA200")
                score += PATTERN_WEIGHTS["PRICE_ABOVE_EMA200"]
            else:
                patterns.append("PRICE_BELOW_EMA200")
                score += PATTERN_WEIGHTS["PRICE_BELOW_EMA200"]

        if not upper.dropna().empty and not lower.dropna().empty and last_close:
            bb_width = (upper.iloc[-1] - lower.iloc[-1]) / last_close
            if bb_width < 0.05:
                patterns.append("BB_SQUEEZE")
                score += PATTERN_WEIGHTS["BB_SQUEEZE"]

        if len(volume) >= 21:
            avg_vol = volume.iloc[-21:-1].mean()
            if avg_vol > 0 and volume.iloc[-1] > 1.5 * avg_vol:
                patterns.append("VOL_BREAKOUT")
                score += PATTERN_WEIGHTS["VOL_BREAKOUT"]

        return patterns, score

    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> tuple[list[str], float]:
        """Nur Engulfing + Morning/Evening Star — siehe Modul-Docstring."""
        patterns: list[str] = []
        score = 0.0
        if len(df) < 3:
            return patterns, score

        o, c = df["Open"], df["Close"]
        o1, c1 = float(o.iloc[-2]), float(c.iloc[-2])
        o2, c2 = float(o.iloc[-1]), float(c.iloc[-1])

        if c1 < o1 and c2 > o2 and c2 >= o1 and o2 <= c1:
            patterns.append("BULLISH_ENGULFING")
            score += PATTERN_WEIGHTS["BULLISH_ENGULFING"]
        elif c1 > o1 and c2 < o2 and o2 >= c1 and c2 <= o1:
            patterns.append("BEARISH_ENGULFING")
            score += PATTERN_WEIGHTS["BEARISH_ENGULFING"]

        o0, c0 = float(o.iloc[-3]), float(c.iloc[-3])
        body0, body1, body2 = abs(c0 - o0), abs(c1 - o1), abs(c2 - o2)
        if body0 > 0 and body1 < body0 * 0.3:
            if c0 < o0 and c2 > o2 and body2 > body0 * 0.5:
                patterns.append("MORNING_STAR")
                score += PATTERN_WEIGHTS["MORNING_STAR"]
            elif c0 > o0 and c2 < o2 and body2 > body0 * 0.5:
                patterns.append("EVENING_STAR")
                score += PATTERN_WEIGHTS["EVENING_STAR"]

        return patterns, score
