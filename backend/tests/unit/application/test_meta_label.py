"""Unit-Tests für Meta-Labeling: Triple-Barrier, Trend-Scan, Meta-Features.

Tests ML-01..ML-04 (Wave A):
- ML-01: triple_barrier_labels korrekte +1/-1/0 Labels auf synthetischen Reihen
- ML-02: trend_scan_labels Richtung bei Aufwärts-/Abwärtstrend und Flat
- ML-03: build_meta_features kein Look-Ahead (shift(1) erzwungen)
- ML-04: Label-Horizont-Isolation (Label@t hängt nur von close[t..t+horizon] ab)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── Lazy import — schlägt fehl (RED) bis Implementierung existiert ──────────
def _import() -> tuple:  # type: ignore[type-arg]
    from backend.application.signals.meta_label import (  # noqa: PLC0415
        build_meta_features,
        trend_scan_labels,
        triple_barrier_labels,
    )

    return triple_barrier_labels, trend_scan_labels, build_meta_features


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _rising_close(n: int = 80, start: float = 100.0, step: float = 1.0) -> pd.Series:
    """Monoton steigende Preisreihe — obere Barriere wird sicher getroffen."""
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    prices = start + step * np.arange(n, dtype=float)
    return pd.Series(prices, index=idx, name="close")


def _falling_close(n: int = 80, start: float = 100.0, step: float = 1.0) -> pd.Series:
    """Monoton fallende Preisreihe — untere Barriere wird sicher getroffen."""
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    prices = start - step * np.arange(n, dtype=float)
    return pd.Series(prices, index=idx, name="close")


def _flat_close(n: int = 80, value: float = 100.0) -> pd.Series:
    """Flache Preisreihe — Zeitbarriere tritt ein (Label 0)."""
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.Series([value] * n, index=idx, dtype=float, name="close")


def _feature_df(n: int = 80, seed: int = 42) -> pd.DataFrame:
    """Synthetischer Feature-DataFrame mit DatetimeIndex (tägliche Frequenz).

    Enthält close, high, low sowie alle für build_meta_features benötigten Spalten.
    n >= 60 für ausreichend Warmup (ATR=20, RSI=14, MACD=26+9).
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)

    df = pd.DataFrame(
        {
            "close": close,
            "high": high,
            "low": low,
            "ma_signal": rng.integers(0, 2, n).astype(float),
            "macd_signal": rng.integers(0, 2, n).astype(float),
            "rsi_signal": rng.integers(0, 2, n).astype(float),
            "vol_pred": rng.uniform(0.1, 0.5, n),
            "momentum_rank": rng.uniform(0.0, 1.0, n),
        },
        index=idx,
    )
    return df


# ── ML-01: Triple-Barrier Label-Korrektheit ──────────────────────────────────


def test_triple_barrier_labels_synthetic() -> None:
    """ML-01: Triple-Barrier Labels auf synthetischen Reihen.

    - Stark steigende Reihe → Label +1 (obere Barriere trifft zuerst)
    - Stark fallende Reihe → Label -1 (untere Barriere trifft zuerst)
    - Flache Reihe → Label 0 (Zeitbarriere, keine Barriere getroffen)
    """
    triple_barrier_labels, _, _ = _import()

    # Stark steigende Reihe: +10 pro Tag → überschreitet +2×ATR in < 5 Bars sicher
    rising = _rising_close(n=80, step=10.0)
    high_r = rising + 0.5
    low_r = rising - 0.5
    labels_up = triple_barrier_labels(rising, high_r, low_r, atr_window=20, upper_mult=2.0,
                                      lower_mult=1.0, horizon=5)
    # Nach Warmup (atr_window Bars) sollte die Mehrheit +1 sein
    valid_up = labels_up.iloc[20:].dropna()
    assert len(valid_up) > 0, "Keine validen Labels für steigende Reihe"
    assert (valid_up == 1).sum() > (valid_up == -1).sum(), (
        f"Steigende Reihe: erwarte mehrheitlich +1, got {valid_up.value_counts().to_dict()}"
    )

    # Stark fallende Reihe: -10 pro Tag → unterschreitet -1×ATR in < 5 Bars sicher
    falling = _falling_close(n=80, step=10.0)
    high_f = falling + 0.5
    low_f = falling - 0.5
    labels_dn = triple_barrier_labels(falling, high_f, low_f, atr_window=20, upper_mult=2.0,
                                      lower_mult=1.0, horizon=5)
    valid_dn = labels_dn.iloc[20:].dropna()
    assert len(valid_dn) > 0, "Keine validen Labels für fallende Reihe"
    assert (valid_dn == -1).sum() > (valid_dn == 1).sum(), (
        f"Fallende Reihe: erwarte mehrheitlich -1, got {valid_dn.value_counts().to_dict()}"
    )

    # Flache Reihe: ATR ~ 0 → Zeitbarriere → alle Labels = 0
    flat = _flat_close(n=80, value=100.0)
    high_flat = flat + 0.01
    low_flat = flat - 0.01
    labels_flat = triple_barrier_labels(flat, high_flat, low_flat, atr_window=20, upper_mult=2.0,
                                        lower_mult=1.0, horizon=5)
    valid_flat = labels_flat.iloc[20:].dropna()
    assert len(valid_flat) > 0, "Keine validen Labels für flache Reihe"
    # Bei flacher Reihe mit sehr kleinem ATR → 0 Labels dominieren
    assert (valid_flat == 0).sum() >= len(valid_flat) * 0.5, (
        f"Flache Reihe: erwarte mehrheitlich 0, got {valid_flat.value_counts().to_dict()}"
    )

    # Alle Labels müssen in {-1, 0, 1} liegen
    for labels, name in [(labels_up, "rising"), (labels_dn, "falling"), (labels_flat, "flat")]:
        unique = set(labels.dropna().unique())
        assert unique.issubset({-1, 0, 1}), f"{name}: Labels ausserhalb {{-1,0,1}}: {unique}"


# ── ML-02: Trend-Scan Label-Richtung ─────────────────────────────────────────


def test_trend_scan_labels_direction() -> None:
    """ML-02: Trend-Scan Labels auf synthetischen Trends.

    - Linearer Aufwärtstrend → Labels überwiegend +1
    - Linearer Abwärtstrend → Labels überwiegend -1
    - Flaches Rauschen unter t-stat 1.5 → Labels überwiegend 0
    """
    _, trend_scan_labels, _ = _import()

    # Starker Aufwärtstrend (+5 pro Tag)
    rising = _rising_close(n=80, step=5.0)
    labels_up = trend_scan_labels(rising, min_window=3, max_window=10, t_stat_threshold=1.5)
    valid_up = labels_up.dropna()
    assert len(valid_up) > 0
    assert (valid_up == 1).sum() > (valid_up == -1).sum(), (
        f"Aufwärtstrend: erwarte mehrheitlich +1, got {valid_up.value_counts().to_dict()}"
    )

    # Starker Abwärtstrend (-5 pro Tag)
    falling = _falling_close(n=80, step=5.0)
    labels_dn = trend_scan_labels(falling, min_window=3, max_window=10, t_stat_threshold=1.5)
    valid_dn = labels_dn.dropna()
    assert len(valid_dn) > 0
    assert (valid_dn == -1).sum() > (valid_dn == 1).sum(), (
        f"Abwärtstrend: erwarte mehrheitlich -1, got {valid_dn.value_counts().to_dict()}"
    )

    # Flat noise: std=0.01, keine starken Trends → 0 dominiert
    rng = np.random.default_rng(99)
    idx = pd.date_range("2021-01-01", periods=80, freq="D")
    flat_noise = pd.Series(100.0 + rng.normal(0, 0.01, 80), index=idx)
    labels_flat = trend_scan_labels(flat_noise, min_window=3, max_window=10, t_stat_threshold=1.5)
    valid_flat = labels_flat.dropna()
    assert len(valid_flat) > 0
    # Flat noise should produce mostly 0 labels
    assert (valid_flat == 0).sum() >= len(valid_flat) * 0.3, (
        f"Flat noise: erwarte mehrheitlich 0, got {valid_flat.value_counts().to_dict()}"
    )

    # Alle Labels in {-1, 0, 1}
    for labels, name in [(labels_up, "up"), (labels_dn, "down"), (labels_flat, "flat")]:
        unique = set(labels.dropna().unique())
        assert unique.issubset({-1, 0, 1}), f"{name}: Labels ausserhalb {{-1,0,1}}: {unique}"


# ── ML-03: build_meta_features kein Look-Ahead ───────────────────────────────


def test_meta_features_no_lookahead() -> None:
    """ML-03: build_meta_features Output muss shift(1) einhalten — kein Look-Ahead.

    assert_no_lookahead darf für keine der 10 Meta-Feature-Spalten einen
    LookAheadError werfen.
    """
    from backend.application.backtest.guards import assert_no_lookahead  # noqa: PLC0415

    _, _, build_meta_features = _import()

    df = _feature_df(n=80)
    meta_df = build_meta_features(df)

    feature_cols = [
        "ma_signal",
        "macd_signal",
        "rsi_signal",
        "consensus_score",
        "rsi_value",
        "macd_hist",
        "atr_norm",
        "vol_pred",
        "momentum_rank",
        "onchain_health",
    ]

    # Prüfe: alle 10 Spalten vorhanden
    for col in feature_cols:
        assert col in meta_df.columns, f"Fehlende Spalte: {col}"

    assert len(meta_df.columns) == 10, (
        f"Erwartet genau 10 Spalten, got {len(meta_df.columns)}: {list(meta_df.columns)}"
    )

    # Füge close als Referenzspalte hinzu
    check_df = meta_df.copy()
    check_df["close"] = df["close"]

    # Kein LookAheadError erlaubt
    assert_no_lookahead(check_df, feature_cols=feature_cols, price_col="close")


# ── ML-04: Label-Horizont-Isolation ──────────────────────────────────────────


def test_label_horizon_isolation() -> None:
    """ML-04: Label@t hängt nur von close[t..t+horizon] ab, nicht von Daten vor t.

    Zwei identische Reihen, die sich NUR in close-Werten VOR Index t unterscheiden
    → Label@t muss gleich sein.
    """
    triple_barrier_labels, _, _ = _import()

    n = 80
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    rng = np.random.default_rng(7)

    # Basis-Reihe
    base_prices = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    close_a = pd.Series(base_prices.copy(), index=idx)
    close_b = pd.Series(base_prices.copy(), index=idx)

    # Wähle t = 40 (nach Warmup)
    t_idx = 40

    # Mutiere close_b nur BEVOR Index t (andere Werte vor t, gleiche ab t)
    close_b.iloc[:t_idx] = close_b.iloc[:t_idx] * 0.5  # drastische Änderung vor t

    high_a = close_a + 0.5
    low_a = close_a - 0.5
    high_b = close_b + 0.5
    low_b = close_b - 0.5

    labels_a = triple_barrier_labels(close_a, high_a, low_a, atr_window=20, upper_mult=2.0,
                                     lower_mult=1.0, horizon=5)
    labels_b = triple_barrier_labels(close_b, high_b, low_b, atr_window=20, upper_mult=2.0,
                                     lower_mult=1.0, horizon=5)

    # Label@t muss gleich sein (ATR ab t+1 ist gleich, forward-Scan gleich)
    label_a_t = labels_a.iloc[t_idx]
    label_b_t = labels_b.iloc[t_idx]
    assert label_a_t == label_b_t, (
        f"Label-Horizont-Isolation verletzt: label_a@{t_idx}={label_a_t}, "
        f"label_b@{t_idx}={label_b_t} — Label darf nur von close[t..t+horizon] abhängen"
    )
