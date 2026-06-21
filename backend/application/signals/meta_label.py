"""Meta-Labeling: Triple-Barrier Labels, Trend-Scan Labels, Meta-Feature-Matrix.

Implements Wave A building blocks for the meta-labeling classifier (López de Prado):

  triple_barrier_labels — ATR-based upper/lower/time barriers → {-1, 0, +1}
  trend_scan_labels     — Forward t-stat scan over windows → {-1, 0, +1}
  build_meta_features   — 10-column shift(1)-safe feature matrix for classifier

Design decisions (locked in 02-CONTEXT.md):
- All features shift(1) before return — Look-Ahead-Guard compatible.
- scipy.stats.linregress imported lazily inside trend_scan_labels (mirrors
  vol_forecast.py LightGBM lazy import pattern).
- ATR via indicators.atr (Wilder's RMA), RSI via indicators.rsi, MACD via indicators.macd.
- Guard NaN/zero ATR → label 0 (Pitfall 4 boundary safety).
- onchain_health defaults to 0.5 when column absent (neutral fill per CONTEXT D Feature Set).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.application.signals.indicators import atr, macd, rsi

__all__ = [
    "build_meta_features",
    "trend_scan_labels",
    "triple_barrier_labels",
]


def triple_barrier_labels(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    atr_window: int = 20,
    upper_mult: float = 2.0,
    lower_mult: float = 1.0,
    horizon: int = 5,
) -> pd.Series:
    """Berechne Triple-Barrier Labels nach López de Prado.

    Für jeden Bar i:
      - upper_barrier = close[i] + upper_mult × ATR[i]
      - lower_barrier = close[i] − lower_mult × ATR[i]
      - Scanne close[i+1 : min(i+horizon+1, n)]
      - Erste Berührung upper → +1, lower → -1, sonst Zeitbarriere → 0

    Parameters
    ----------
    close:
        Schlusskurs-Zeitreihe.
    high:
        Tageshöchstkurs (für ATR-Berechnung).
    low:
        Tagestiefstkurs (für ATR-Berechnung).
    atr_window:
        Lookback-Fenster für ATR (Standard 20).
    upper_mult:
        ATR-Multiplikator für obere Barriere (Standard 2.0).
    lower_mult:
        ATR-Multiplikator für untere Barriere (Standard 1.0, asymmetrisch).
    horizon:
        Maximale Anzahl Bars für den Forward-Scan (Zeitbarriere).

    Returns
    -------
    pd.Series[int]
        Labels {-1, 0, +1} mit gleichem Index wie close.
    """
    atr_series = atr(high, low, close, window=atr_window)
    close_arr = close.to_numpy(dtype=float)
    atr_arr = atr_series.to_numpy(dtype=float)
    n = len(close_arr)
    labels = np.zeros(n, dtype=int)

    for i in range(n):
        atr_val = atr_arr[i]
        # Guard: NaN oder zero ATR → Zeitbarriere (Label 0)
        if atr_val == 0.0 or np.isnan(atr_val):
            labels[i] = 0
            continue

        upper = close_arr[i] + upper_mult * atr_val
        lower = close_arr[i] - lower_mult * atr_val

        # Scan forward window — boundary-safe (Pitfall 4)
        end = min(i + horizon + 1, n)
        label = 0
        for j in range(i + 1, end):
            p = close_arr[j]
            if np.isnan(p):
                continue
            if p >= upper:
                label = 1
                break
            if p <= lower:
                label = -1
                break
        labels[i] = label

    return pd.Series(labels, index=close.index, dtype=int)


def trend_scan_labels(
    close: pd.Series,
    min_window: int = 3,
    max_window: int = 10,
    t_stat_threshold: float = 1.5,
) -> pd.Series:
    """Berechne Trend-Scan Labels via linearer Regression über Forward-Fenster.

    Für jeden Bar i: scanne alle Fenster w in [min_window, max_window]; für jedes
    Fenster wird scipy.stats.linregress auf die Forward-Preisreihe gefittet. Das
    Label ist sign(slope) des Fensters mit dem grössten |t-Statistik|, falls
    max|t| >= t_stat_threshold, sonst 0.

    Anti-Pattern: NICHT rvalue verwenden — t-stat = slope / stderr (RESEARCH §3).

    Parameters
    ----------
    close:
        Schlusskurs-Zeitreihe.
    min_window:
        Minimale Fenstergrösse für den Forward-Scan (Standard 3).
    max_window:
        Maximale Fenstergrösse für den Forward-Scan (Standard 10).
    t_stat_threshold:
        Mindestwert des |t-Statistik| für ein gültiges Label (Standard 1.5).

    Returns
    -------
    pd.Series[int]
        Labels {-1, 0, +1} mit gleichem Index wie close.
    """
    from scipy.stats import linregress  # noqa: PLC0415

    close_arr = close.to_numpy(dtype=float)
    n = len(close_arr)
    labels = np.zeros(n, dtype=int)

    for i in range(n):
        best_tstat = 0.0
        best_slope = 0.0

        for w in range(min_window, max_window + 1):
            end = i + w
            if end > n:
                break
            y = close_arr[i:end]
            if np.any(np.isnan(y)):
                continue
            x = np.arange(w, dtype=float)
            result = linregress(x, y)
            # t-stat = slope / stderr (NOT rvalue — Anti-Pattern RESEARCH §3)
            stderr = float(result.stderr)
            slope = float(result.slope)
            if np.isnan(stderr) or np.isnan(slope):
                continue
            # Perfectly linear fit: stderr=0 → infinite t-stat (definitive trend)
            if stderr == 0.0:
                t_stat = np.sign(slope) * 1e9 if slope != 0.0 else 0.0
            else:
                t_stat = slope / stderr
            if abs(t_stat) > abs(best_tstat):
                best_tstat = t_stat
                best_slope = slope

        if abs(best_tstat) >= t_stat_threshold:
            labels[i] = int(np.sign(best_slope))
        else:
            labels[i] = 0

    return pd.Series(labels, index=close.index, dtype=int)


def build_meta_features(df: pd.DataFrame) -> pd.DataFrame:
    """Erzeuge 10-spaltige Meta-Feature-Matrix mit shift(1) für Classifier.

    Alle abgeleiteten Spalten werden shift(1) BEVOR sie zurückgegeben werden.
    Dies stellt sicher, dass Feature@t nur Daten <= t-1 verwendet (kein Look-Ahead).

    Erwartete Input-Spalten in df:
      close, high (optional, fallback=close), low (optional, fallback=close),
      ma_signal, macd_signal, rsi_signal,
      vol_pred (optional, NaN-fill), momentum_rank (optional, NaN-fill),
      onchain_health (optional, Default=0.5)

    Parameters
    ----------
    df:
        DataFrame mit mindestens 'close', 'ma_signal', 'macd_signal', 'rsi_signal'.

    Returns
    -------
    pd.DataFrame
        Genau 10 Spalten: ma_signal, macd_signal, rsi_signal, consensus_score,
        rsi_value, macd_hist, atr_norm, vol_pred, momentum_rank, onchain_health.
        Alle shift(1) angewendet.
    """
    close = df["close"]
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close

    # ── Sub-scores: shift(1) auf Eingabe-Signale ─────────────────────────────
    ma_s = df["ma_signal"].shift(1)
    macd_s = df["macd_signal"].shift(1)
    rsi_s = df["rsi_signal"].shift(1)

    # consensus_score = Mittelwert der bereits verschobenen Sub-Scores
    consensus = (ma_s + macd_s + rsi_s) / 3.0

    # ── Rohe Indikatoren: shift(1) nach Berechnung ───────────────────────────
    rsi_val = rsi(close).shift(1)

    _macd_line, _signal_line, macd_histogram = macd(close)
    macd_hist_shifted = macd_histogram.shift(1)

    atr_series = atr(high, low, close)
    # atr_norm = ATR / close (normalisierte Vol), NaN wenn close=0
    atr_norm = (atr_series / close.replace(0, np.nan)).shift(1)

    # ── Pass-through Features: aus df lesen + shift(1) ───────────────────────
    vol_pred_col = df["vol_pred"].shift(1) if "vol_pred" in df.columns else pd.Series(
        np.nan, index=df.index
    )
    momentum_rank_col = df["momentum_rank"].shift(1) if "momentum_rank" in df.columns else (
        pd.Series(np.nan, index=df.index)
    )

    # onchain_health: 0.5 als neutraler Default wenn nicht vorhanden
    if "onchain_health" in df.columns:
        onchain = df["onchain_health"].shift(1)
    else:
        onchain = pd.Series(0.5, index=df.index, dtype=float)

    result = pd.DataFrame(
        {
            "ma_signal": ma_s,
            "macd_signal": macd_s,
            "rsi_signal": rsi_s,
            "consensus_score": consensus,
            "rsi_value": rsi_val,
            "macd_hist": macd_hist_shifted,
            "atr_norm": atr_norm,
            "vol_pred": vol_pred_col,
            "momentum_rank": momentum_rank_col,
            "onchain_health": onchain,
        },
        index=df.index,
    )
    return result
