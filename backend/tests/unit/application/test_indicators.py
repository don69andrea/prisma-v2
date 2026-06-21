"""Unit tests for technical indicators — RED phase (test-first).

Each indicator is validated against the `ta` library reference implementation.
Delta < 1e-6 is required for all comparisons.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

pytestmark = pytest.mark.unit

RNG_SEED = 42
N_BARS = 100


@pytest.fixture()
def sample_close() -> pd.Series:
    """Synthetic geometric random walk with seed 42 — 100 bars."""
    rng = np.random.default_rng(RNG_SEED)
    log_returns = rng.normal(0.001, 0.02, N_BARS)
    prices = 100.0 * np.exp(np.cumsum(log_returns))
    return pd.Series(prices, name="close")


@pytest.fixture()
def sample_ohlc(sample_close: pd.Series) -> pd.DataFrame:
    """Synthetic OHLC DataFrame derived from close prices."""
    rng = np.random.default_rng(RNG_SEED + 1)
    noise = rng.uniform(0.005, 0.015, N_BARS)
    close = sample_close.values
    high = close * (1.0 + noise)
    low = close * (1.0 - noise)
    open_ = close * (1.0 + rng.uniform(-0.01, 0.01, N_BARS))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=sample_close.index,
    )


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------


def test_sma_matches_ta(sample_close: pd.Series) -> None:
    """SMA implementation must match ta.trend.SMAIndicator within 1e-6."""
    from backend.application.signals.indicators import sma

    window = 20
    own = sma(sample_close, window)
    ref = SMAIndicator(close=sample_close, window=window).sma_indicator()

    diff = (own - ref).abs().dropna()
    assert diff.max() < 1e-6, f"Max delta {diff.max():.2e} exceeds 1e-6"

    # No NaN after warmup period
    valid = own.iloc[window - 1 :]
    assert not valid.isna().any(), "NaN found in valid range"


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------


def test_ema_matches_ta(sample_close: pd.Series) -> None:
    """EMA implementation must match ta.trend.EMAIndicator within 1e-6."""
    from backend.application.signals.indicators import ema

    window = 20
    own = ema(sample_close, window)
    ref = EMAIndicator(close=sample_close, window=window).ema_indicator()

    diff = (own - ref).abs().dropna()
    assert diff.max() < 1e-6, f"Max delta {diff.max():.2e} exceeds 1e-6"

    valid = own.iloc[window - 1 :]
    assert not valid.isna().any(), "NaN found in valid range"


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


def test_rsi_matches_ta(sample_close: pd.Series) -> None:
    """RSI implementation must match ta.momentum.RSIIndicator within 1e-6."""
    from backend.application.signals.indicators import rsi

    window = 14
    own = rsi(sample_close, window)
    ref = RSIIndicator(close=sample_close, window=window).rsi()

    diff = (own - ref).abs().dropna()
    assert diff.max() < 1e-6, f"Max delta {diff.max():.2e} exceeds 1e-6"

    valid = own.iloc[window:]
    assert not valid.isna().any(), "NaN found in valid range"


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


def test_macd_matches_ta(sample_close: pd.Series) -> None:
    """MACD line, signal line, and histogram must each match ta.trend.MACD within 1e-6."""
    from backend.application.signals.indicators import macd

    fast, slow, signal_window = 12, 26, 9
    own_line, own_signal, own_hist = macd(sample_close, fast, slow, signal_window)

    ta_macd = MACD(
        close=sample_close,
        window_fast=fast,
        window_slow=slow,
        window_sign=signal_window,
    )
    ref_line = ta_macd.macd()
    ref_signal = ta_macd.macd_signal()
    ref_hist = ta_macd.macd_diff()

    for name, own, ref in [
        ("macd_line", own_line, ref_line),
        ("signal_line", own_signal, ref_signal),
        ("histogram", own_hist, ref_hist),
    ]:
        diff = (own - ref).abs().dropna()
        assert diff.max() < 1e-6, f"[{name}] Max delta {diff.max():.2e} exceeds 1e-6"

    # No NaN after the slow+signal warmup
    warmup = slow + signal_window - 2
    for name, series in [("line", own_line), ("signal", own_signal), ("hist", own_hist)]:
        valid = series.iloc[warmup:]
        assert not valid.isna().any(), f"NaN in valid range for {name}"


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


def test_bollinger_matches_ta(sample_close: pd.Series) -> None:
    """Bollinger upper/middle/lower bands must match ta.volatility.BollingerBands within 1e-6."""
    from backend.application.signals.indicators import bollinger

    window = 20
    std = 2.0
    own_upper, own_mid, own_lower = bollinger(sample_close, window, std)

    bb = BollingerBands(close=sample_close, window=window, window_dev=std)
    ref_upper = bb.bollinger_hband()
    ref_mid = bb.bollinger_mavg()
    ref_lower = bb.bollinger_lband()

    for name, own, ref in [
        ("upper", own_upper, ref_upper),
        ("middle", own_mid, ref_mid),
        ("lower", own_lower, ref_lower),
    ]:
        diff = (own - ref).abs().dropna()
        assert diff.max() < 1e-6, f"[{name}] Max delta {diff.max():.2e} exceeds 1e-6"

    valid_upper = own_upper.iloc[window - 1 :]
    assert not valid_upper.isna().any(), "NaN in upper band valid range"


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------


def test_atr_requires_ohlc(sample_ohlc: pd.DataFrame) -> None:
    """ATR implementation must match ta.volatility.AverageTrueRange within 1e-6."""
    from backend.application.signals.indicators import atr

    window = 14
    own = atr(
        high=sample_ohlc["high"],
        low=sample_ohlc["low"],
        close=sample_ohlc["close"],
        window=window,
    )

    ref = AverageTrueRange(
        high=sample_ohlc["high"],
        low=sample_ohlc["low"],
        close=sample_ohlc["close"],
        window=window,
    ).average_true_range()

    diff = (own - ref).abs().dropna()
    assert diff.max() < 1e-6, f"Max delta {diff.max():.2e} exceeds 1e-6"

    valid = own.iloc[window:]
    assert not valid.isna().any(), "NaN found in valid range"


# ---------------------------------------------------------------------------
# Return type checks
# ---------------------------------------------------------------------------


def test_sma_returns_series(sample_close: pd.Series) -> None:
    """sma() must return a pd.Series aligned to the input index."""
    from backend.application.signals.indicators import sma

    result = sma(sample_close, 20)
    assert isinstance(result, pd.Series)
    assert result.index.equals(sample_close.index)


def test_macd_returns_three_series(sample_close: pd.Series) -> None:
    """macd() must return a 3-tuple of pd.Series."""
    from backend.application.signals.indicators import macd

    result = macd(sample_close)
    assert len(result) == 3
    assert all(isinstance(s, pd.Series) for s in result)
