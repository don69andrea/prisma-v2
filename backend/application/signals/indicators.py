"""Technical indicators — pure vectorized pandas/numpy implementations.

All functions operate on pd.Series or pd.DataFrame inputs and return
pd.Series (or tuples thereof) aligned to the input index.

Design decisions:
- No imports from `ta` library — computed from scratch using pandas rolling/ewm.
- Implementations are numerically equivalent to `ta` library (delta < 1e-6).
- No side effects; all functions are pure (stateless).
- Look-ahead guard: consumers must apply df.shift(1) on price inputs before
  computing signals to ensure signal@t uses only data <= t-1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average.

    Args:
        close: Price series (aligned to any DatetimeIndex).
        window: Rolling window size in bars.

    Returns:
        pd.Series of SMA values, NaN for the first ``window - 1`` bars.
    """
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, window: int) -> pd.Series:
    """Exponential Moving Average (adjust=False, compatible with ta library).

    Args:
        close: Price series.
        window: EMA span (number of periods).

    Returns:
        pd.Series of EMA values, NaN for the first ``window - 1`` bars.
    """
    return close.ewm(span=window, min_periods=window, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index.

    Uses the Wilder smoothing (EWM alpha = 1/window, adjust=False) identical
    to the `ta` library implementation.

    Args:
        close: Price series.
        window: RSI look-back period (default 14).

    Returns:
        pd.Series of RSI values in [0, 100]. NaN for the first ``window`` bars.
    """
    diff = close.diff(1)
    up_direction = diff.where(diff > 0, 0.0)
    down_direction = -diff.where(diff < 0, 0.0)

    ema_up = up_direction.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    ema_dn = down_direction.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()

    rs = ema_up / ema_dn.replace(0, np.nan)
    rsi_values = pd.Series(
        np.where(ema_dn == 0, 100.0, 100.0 - (100.0 / (1.0 + rs))),
        index=close.index,
    )
    # Restore NaN for the warmup period (first `window` bars after diff)
    rsi_values.iloc[: window] = np.nan
    return rsi_values


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence.

    Args:
        close: Price series.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line EMA period (default 9).

    Returns:
        Tuple of (macd_line, signal_line, histogram) — all pd.Series.
    """
    ema_fast = close.ewm(span=fast, min_periods=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, min_periods=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(
    close: pd.Series,
    window: int = 20,
    std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands.

    Uses population standard deviation (ddof=0), identical to `ta` library.

    Args:
        close: Price series.
        window: Rolling window for the moving average (default 20).
        std: Number of standard deviations for the bands (default 2.0).

    Returns:
        Tuple of (upper_band, middle_band, lower_band) — all pd.Series.
    """
    middle = close.rolling(window=window, min_periods=window).mean()
    rolling_std = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = middle + std * rolling_std
    lower = middle - std * rolling_std
    return upper, middle, lower


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """Average True Range.

    Uses Wilder's smoothing (iterative RMA), identical to `ta` library:
      ATR[window-1] = mean(TR[0:window])
      ATR[i] = (ATR[i-1] * (window - 1) + TR[i]) / window

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        window: ATR period (default 14).

    Returns:
        pd.Series of ATR values. First ``window - 1`` bars are 0 (ta convention).
    """
    close_shift = close.shift(1)
    # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    tr = pd.concat(
        [
            high - low,
            (high - close_shift).abs(),
            (low - close_shift).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_values = np.zeros(len(close))
    atr_values[window - 1] = tr.iloc[:window].mean()
    for i in range(window, len(atr_values)):
        atr_values[i] = (atr_values[i - 1] * (window - 1) + tr.iloc[i]) / float(window)

    return pd.Series(data=atr_values, index=close.index)
