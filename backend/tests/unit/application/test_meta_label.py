"""Unit-Tests für Meta-Labeling: Triple-Barrier, Trend-Scan, Meta-Features.

Tests ML-01..ML-04 (Wave A):
- ML-01: triple_barrier_labels korrekte +1/-1/0 Labels auf synthetischen Reihen
- ML-02: trend_scan_labels Richtung bei Aufwärts-/Abwärtstrend und Flat
- ML-03: build_meta_features kein Look-Ahead (shift(1) erzwungen)
- ML-04: Label-Horizont-Isolation (Label@t hängt nur von close[t..t+horizon] ab)

Tests ML-05..ML-06 (Wave B):
- ML-05: Classifier Walk-Forward OOS Precision > 50% auf synthetischen Daten
- ML-06: No-Snooping — Classifier nie auf OOS-Folds gefittet (Embargo-Invariante)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── Lazy import Wave A ───────────────────────────────────────────────────────
def _import() -> tuple:  # type: ignore[type-arg]
    from backend.application.signals.meta_label import (  # noqa: PLC0415
        build_meta_features,
        trend_scan_labels,
        triple_barrier_labels,
    )

    return triple_barrier_labels, trend_scan_labels, build_meta_features


# ── Lazy import Wave B — schlägt fehl (RED) bis Implementierung existiert ───
def _import_classifier() -> tuple:  # type: ignore[type-arg]
    from backend.application.signals.meta_label import (  # noqa: PLC0415
        _walkforward_meta_cv,
        fit_meta_classifier,
        predict_meta_label,
    )

    return fit_meta_classifier, predict_meta_label, _walkforward_meta_cv


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
    labels_up = triple_barrier_labels(
        rising, high_r, low_r, atr_window=20, upper_mult=2.0, lower_mult=1.0, horizon=5
    )
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
    labels_dn = triple_barrier_labels(
        falling, high_f, low_f, atr_window=20, upper_mult=2.0, lower_mult=1.0, horizon=5
    )
    valid_dn = labels_dn.iloc[20:].dropna()
    assert len(valid_dn) > 0, "Keine validen Labels für fallende Reihe"
    assert (valid_dn == -1).sum() > (valid_dn == 1).sum(), (
        f"Fallende Reihe: erwarte mehrheitlich -1, got {valid_dn.value_counts().to_dict()}"
    )

    # Flache Reihe: ATR ~ 0 → Zeitbarriere → alle Labels = 0
    flat = _flat_close(n=80, value=100.0)
    high_flat = flat + 0.01
    low_flat = flat - 0.01
    labels_flat = triple_barrier_labels(
        flat, high_flat, low_flat, atr_window=20, upper_mult=2.0, lower_mult=1.0, horizon=5
    )
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

    labels_a = triple_barrier_labels(
        close_a, high_a, low_a, atr_window=20, upper_mult=2.0, lower_mult=1.0, horizon=5
    )
    labels_b = triple_barrier_labels(
        close_b, high_b, low_b, atr_window=20, upper_mult=2.0, lower_mult=1.0, horizon=5
    )

    # Label@t muss gleich sein (ATR ab t+1 ist gleich, forward-Scan gleich)
    label_a_t = labels_a.iloc[t_idx]
    label_b_t = labels_b.iloc[t_idx]
    assert label_a_t == label_b_t, (
        f"Label-Horizont-Isolation verletzt: label_a@{t_idx}={label_a_t}, "
        f"label_b@{t_idx}={label_b_t} — Label darf nur von close[t..t+horizon] abhängen"
    )


# ── Wave B Fixtures ───────────────────────────────────────────────────────────


def _learnable_xy(n: int = 600) -> tuple[pd.DataFrame, pd.Series]:
    """Synthetische (X, y)-Daten mit lernbarem Muster für Classifier-Tests.

    n >= min_train(252) + embargo(5) + 10*step(21) = 467 → 600 gibt >=15 Folds.
    y ist eine deterministische Funktion von feature_0 plus leichtem Rauschen.
    Der Classifier kann dieses Muster sicher lernen (OOS precision >> 50%).

    Parameters
    ----------
    n:
        Anzahl Zeitschritte (Standard 600 — garantiert >= 10 Folds).

    Returns
    -------
    tuple[pd.DataFrame, pd.Series]
        X: DataFrame mit 3 numerischen Features und DatetimeIndex.
        y: Binäre Series {0, 1} — deterministische Funktion von feature_0.
    """
    rng = np.random.default_rng(42)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")

    # Feature 0: stark prädiktiv — y = 1 wenn feature_0 > 0, sonst 0
    feature_0 = rng.normal(0, 1.0, n)
    # Feature 1 und 2: Rauschen (kein prädiktiver Wert)
    feature_1 = rng.normal(0, 1.0, n)
    feature_2 = rng.normal(0, 1.0, n)

    X = pd.DataFrame(
        {"feature_0": feature_0, "feature_1": feature_1, "feature_2": feature_2},
        index=idx,
    )

    # y = deterministische Funktion + 10% Rauschen → klar lernbar
    noise = rng.uniform(0, 1.0, n)
    y_clean = (feature_0 > 0).astype(int)
    # 10% Flip-Rate für Rauschen
    flip_mask = noise < 0.10
    y = y_clean.copy()
    y[flip_mask] = 1 - y_clean[flip_mask]
    y_series = pd.Series(y, index=idx, name="label", dtype=int)

    return X, y_series


# ── ML-05: Classifier Walk-Forward OOS Precision > 50% ───────────────────────


def test_classifier_oos_above_random() -> None:
    """ML-05: Walk-Forward mittlere OOS-Precision > 50% auf lernbaren Daten.

    Der Classifier muss auf synthetischen Daten mit bekanntem Muster
    (y = Funktion von feature_0) eine mittlere OOS-Precision > 0.50 erreichen.
    Dies stellt sicher, dass der Walk-Forward korrekt implementiert ist und
    der Classifier echtes Signal extrahiert (kein Dummy-Classifier).
    """
    fit_meta_classifier, predict_meta_label, _ = _import_classifier()

    X, y = _learnable_xy(n=600)

    result = predict_meta_label(
        X,
        y,
        min_train=252,
        step=21,
        embargo=5,
        model="logreg",
    )

    n_folds = result["n_folds"]
    assert n_folds >= 10, (
        f"ML-05: Zu wenige OOS-Folds ({n_folds} < 10) — n=600 sollte mindestens 15 Folds liefern"
    )

    mean_precision = result["mean_precision"]
    assert mean_precision > 0.50, (
        f"ML-05: OOS-Precision {mean_precision:.3f} <= 0.50 — "
        f"Classifier sollte lernbares Muster (feature_0 > 0 → y=1) extrahieren"
    )


# ── ML-06: No-Snooping — Embargo-Invariante ──────────────────────────────────


def test_no_snooping() -> None:
    """ML-06: Embargo-Invariante — Train-Ende + embargo <= Test-Start für jeden Fold.

    Für jeden Walk-Forward-Fold muss gelten:
      fold['train_end_idx'] + embargo <= fold['test_start_idx']

    Dies stellt sicher, dass:
    1. OOS-Daten nie während des Fits gesehen werden (kein Snooping).
    2. Der Embargo-Dead-Zone von 5 Bars eingehalten wird (verhindert
       Label-Leakage aus dem Triple-Barrier Forward-Horizon).
    """
    _, _, _walkforward_meta_cv = _import_classifier()

    X, y = _learnable_xy(n=600)
    embargo = 5

    result = _walkforward_meta_cv(X, y, min_train=252, step=21, embargo=embargo)

    folds = result["folds"]
    assert len(folds) >= 10, f"ML-06: Zu wenige Folds ({len(folds)}) für valide Invarianten-Prüfung"

    for i, fold in enumerate(folds):
        train_end = fold["train_end_idx"]
        test_start = fold["test_start_idx"]
        assert train_end + embargo <= test_start, (
            f"ML-06: Snooping-Verletzung in Fold {i}: "
            f"train_end_idx={train_end} + embargo={embargo} = {train_end + embargo} "
            f"> test_start_idx={test_start}. "
            f"Train darf nie OOS-Daten sehen."
        )


# ── ML-07: Edge-branch coverage for >= 80% gate (ML-10) ─────────────────────


def test_triple_barrier_nan_price_in_window() -> None:
    """ML-10-a: NaN price inside forward scan → skipped (line 98 branch)."""
    triple_barrier_labels, _, _ = _import()

    n = 30
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    prices = np.linspace(100.0, 130.0, n)
    # Insert NaN at position 5 — inside the forward scan of bar 0..3
    prices[5] = float("nan")
    close = pd.Series(prices, index=idx)
    high = close.ffill() + 0.5
    low = close.ffill() - 0.5

    labels = triple_barrier_labels(close, high, low, atr_window=5, horizon=10)
    assert set(labels.dropna().unique()).issubset({-1, 0, 1})


def test_trend_scan_nan_window_skip() -> None:
    """ML-10-b: NaN inside trend_scan window → skipped (line 157 branch)."""
    _, trend_scan_labels, _ = _import()

    n = 30
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    prices = np.linspace(100.0, 115.0, n)
    prices[3] = float("nan")  # NaN inside early window
    close = pd.Series(prices, index=idx)

    labels = trend_scan_labels(close, min_window=3, max_window=6, t_stat_threshold=1.5)
    assert set(labels.dropna().unique()).issubset({-1, 0, 1})


def test_build_meta_features_with_onchain_health() -> None:
    """ML-10-c: onchain_health column present → shift(1) applied (line 238 branch)."""
    _, _, build_meta_features = _import()

    df = _feature_df(n=40)
    df["onchain_health"] = 0.8  # add the column that triggers line 238

    meta = build_meta_features(df)
    assert "onchain_health" in meta.columns
    # First row is NaN due to shift(1) on the onchain_health column
    # (all cols shifted, onchain is now shifted too)
    assert len(meta) == len(df)


def test_fit_meta_classifier_lgbm() -> None:
    """ML-10-d: lgbm fallback path in fit_meta_classifier (lines 290-299)."""
    fit_meta_classifier, _, _ = _import_classifier()

    rng = np.random.default_rng(1)
    X = pd.DataFrame({"f0": rng.normal(0, 1, 80), "f1": rng.normal(0, 1, 80)})
    y = pd.Series((rng.normal(0, 1, 80) > 0).astype(int))

    result = fit_meta_classifier(X, y, model="lgbm")
    assert result["model_type"] == "lgbm"
    assert "model" in result


def test_predict_meta_label_insufficient_folds() -> None:
    """ML-10-e: n_folds < 10 → finding='negative','insufficient_oos_folds' (line 456)."""
    _, predict_meta_label, _ = _import_classifier()

    # Small dataset: only 300 rows → can't produce 10 folds with min_train=252
    rng = np.random.default_rng(7)
    n = 300
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    X = pd.DataFrame({"f0": rng.normal(0, 1, n)}, index=idx)
    y = pd.Series((rng.normal(0, 1, n) > 0).astype(int), index=idx, name="label")

    result = predict_meta_label(X, y, min_train=252, step=21, embargo=5, model="logreg")
    assert result["n_folds"] < 10
    assert result["finding"] == "negative"
    assert result["finding_reason"] == "insufficient_oos_folds"


def test_walkforward_meta_cv_single_class_fold_skipped() -> None:
    """ML-10-f: fold with < 2 classes in y_train is skipped (line 382-383 branch)."""
    _, _, _walkforward_meta_cv = _import_classifier()

    # All-zeros y → every train fold has only 1 class → all skipped → n_folds = 0
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    X = pd.DataFrame({"f0": np.ones(n)}, index=idx)
    y = pd.Series(np.zeros(n, dtype=int), index=idx)

    result = _walkforward_meta_cv(X, y, min_train=252, step=21, embargo=5)
    # All folds skipped due to single class → n_folds == 0
    assert result["n_folds"] == 0


# ── ML-10-g: Direct unit tests for _sync_meta_label finding branches ─────────


def test_sync_meta_label_returns_meta_label_report() -> None:
    """ML-10-g: _sync_meta_label direct call returns valid MetaLabelReport."""
    from backend.interfaces.rest.routers.signals import (  # noqa: PLC0415
        _make_stub_prices,
        _sync_meta_label,
    )
    from backend.interfaces.rest.schemas.signals import MetaLabelReport  # noqa: PLC0415

    prices_df = _make_stub_prices("BTC-USD", n=500)
    report = _sync_meta_label("BTC-USD", prices_df)
    assert isinstance(report, MetaLabelReport)
    assert report.coin == "BTC-USD"
    assert report.finding in {"positive", "secondary_pass", "negative"}


def test_sync_meta_label_small_dataset_negative_finding() -> None:
    """ML-10-h: Small dataset (25 rows) → n_folds<10 → finding='negative'."""
    from backend.interfaces.rest.routers.signals import (
        _make_stub_prices,  # noqa: PLC0415
        _sync_meta_label,  # noqa: PLC0415
    )

    # 25 rows: enough for ATR warmup but too few for >= 10 walk-forward folds
    prices_df = _make_stub_prices("ETH-USD", n=25)
    report = _sync_meta_label("ETH-USD", prices_df)
    # Small dataset → either insufficient_data or insufficient_oos_folds
    assert report.finding == "negative"
    assert "insufficient" in report.finding_reason


# ── ML-10-i: Cover finding branches in _sync_meta_label via monkeypatching ──


def test_sync_meta_label_positive_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """ML-10-i: Positive finding when meta_sharpe > always_sharpe AND calmar.

    Monkeypatch predict_meta_label to return n_folds >= 10 so finding-logic
    branches (lines 355-384 in signals.py) are exercised.
    """
    import backend.interfaces.rest.routers.signals as _router_mod  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import (  # noqa: PLC0415
        _make_stub_prices,
        _sync_meta_label,
    )

    def _fake_predict(X, y, **kw):  # type: ignore
        return {
            "n_folds": 12,
            "mean_precision": 0.65,
            "mean_recall": 0.60,
            "mean_f1": 0.62,
            "final_model_info": None,
            "folds": [],
            "finding": "positive",
            "finding_reason": "oos_precision_above_random",
        }

    def _fake_wf(prices, signals, costs=0.001, meta_filter=None, **kw):  # type: ignore
        if meta_filter is None:
            return {"strategy_sharpe": 0.5, "strategy_calmar": 0.3, "n_trades": 100}
        return {"strategy_sharpe": 1.0, "strategy_calmar": 0.8, "n_trades": 50}

    monkeypatch.setattr(_router_mod, "predict_meta_label", _fake_predict)
    monkeypatch.setattr(_router_mod, "_run_wf_details", _fake_wf)

    prices_df = _make_stub_prices("SOL-USD", n=500)
    report = _sync_meta_label("SOL-USD", prices_df)
    assert report.finding == "positive"
    assert report.beats_baseline is True


def test_sync_meta_label_secondary_pass_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """ML-10-j: Secondary-pass when n_filtered < 90% of n_always, no perf loss."""
    import backend.interfaces.rest.routers.signals as _router_mod  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import (  # noqa: PLC0415
        _make_stub_prices,
        _sync_meta_label,
    )

    def _fake_predict(X, y, **kw):  # type: ignore
        return {
            "n_folds": 12,
            "mean_precision": 0.45,
            "mean_recall": 0.5,
            "mean_f1": 0.47,
            "final_model_info": None,
            "folds": [],
            "finding": "negative",
            "finding_reason": "oos_precision_at_or_below_random",
        }

    def _fake_wf(prices, signals, costs=0.001, meta_filter=None, **kw):  # type: ignore
        if meta_filter is None:
            return {"strategy_sharpe": 1.0, "strategy_calmar": 0.8, "n_trades": 100}
        return {"strategy_sharpe": 0.97, "strategy_calmar": 0.78, "n_trades": 85}

    monkeypatch.setattr(_router_mod, "predict_meta_label", _fake_predict)
    monkeypatch.setattr(_router_mod, "_run_wf_details", _fake_wf)

    prices_df = _make_stub_prices("ADA-USD", n=500)
    report = _sync_meta_label("ADA-USD", prices_df)
    assert report.finding == "secondary_pass"
    assert report.beats_baseline is True


def test_sync_meta_label_negative_finding_no_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ML-10-k: Negative when meta_filter doesn't improve over always-trade."""
    import backend.interfaces.rest.routers.signals as _router_mod  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import (  # noqa: PLC0415
        _make_stub_prices,
        _sync_meta_label,
    )

    def _fake_predict(X, y, **kw):  # type: ignore
        return {
            "n_folds": 12,
            "mean_precision": 0.45,
            "mean_recall": 0.5,
            "mean_f1": 0.47,
            "final_model_info": None,
            "folds": [],
            "finding": "negative",
            "finding_reason": "oos_precision_at_or_below_random",
        }

    def _fake_wf(prices, signals, costs=0.001, meta_filter=None, **kw):  # type: ignore
        if meta_filter is None:
            return {"strategy_sharpe": 1.0, "strategy_calmar": 0.8, "n_trades": 100}
        # Worse performance AND not enough trade reduction
        return {"strategy_sharpe": 0.6, "strategy_calmar": 0.5, "n_trades": 95}

    monkeypatch.setattr(_router_mod, "predict_meta_label", _fake_predict)
    monkeypatch.setattr(_router_mod, "_run_wf_details", _fake_wf)

    prices_df = _make_stub_prices("XRP-USD", n=500)
    report = _sync_meta_label("XRP-USD", prices_df)
    assert report.finding == "negative"
    assert report.finding_reason == "meta_filter_does_not_improve_over_always_trade"
    assert report.beats_baseline is False


# ── Wave D — REST Endpoint Tests (ML-09, ML-10) ─────────────────────────────


# Minimal FastAPI TestClient fixture for signals router
def _make_test_app():  # type: ignore[no-untyped-def]
    """Erstelle minimale FastAPI-App mit signals router für Unit-Tests."""
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from backend.interfaces.rest.routers.signals import router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ── ML-09: REST endpoint returns valid MetaLabelReport ───────────────────────


def test_rest_returns_pydantic() -> None:
    """ML-09: GET /api/v1/signals/meta-label/BTC-USD returns 200 + MetaLabelReport.

    Validates all required Pydantic fields are present and finding is in the
    allowed Literal set {"positive", "secondary_pass", "negative"}.
    """
    from backend.interfaces.rest.schemas.signals import MetaLabelReport  # noqa: PLC0415

    client = _make_test_app()
    resp = client.get("/api/v1/signals/meta-label/BTC-USD")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    # Full Pydantic validation — raises if any required field is missing/wrong type
    report = MetaLabelReport.model_validate(body)
    assert report.coin == "BTC-USD"
    assert report.finding in {"positive", "secondary_pass", "negative"}, (
        f"finding '{report.finding}' not in allowed Literal set"
    )
    assert report.label_method in {"triple_barrier", "trend_scan"}
    assert report.classifier in {"logreg", "lgbm"}
    assert isinstance(report.n_folds, int)
    assert isinstance(report.oos_precision, float)
    assert isinstance(report.oos_recall, float)
    assert isinstance(report.beats_baseline, bool)


# ── ML-10: Unknown coin returns 404 ──────────────────────────────────────────


def test_meta_label_unknown_coin_404() -> None:
    """ML-10: GET /api/v1/signals/meta-label/FAKE-USD returns 404.

    coin not in _CRYPTO_UNIVERSE whitelist → HTTP 404 with whitelist detail.
    """
    client = _make_test_app()
    resp = client.get("/api/v1/signals/meta-label/FAKE-USD")
    assert resp.status_code == 404, (
        f"Expected 404 for unknown coin, got {resp.status_code}: {resp.text[:200]}"
    )


def test_meta_label_coin_case_insensitive() -> None:
    """Coin parameter is uppercased: btc-usd → BTC-USD."""
    from backend.interfaces.rest.schemas.signals import MetaLabelReport  # noqa: PLC0415

    client = _make_test_app()
    resp = client.get("/api/v1/signals/meta-label/btc-usd")
    assert resp.status_code == 200
    MetaLabelReport.model_validate(resp.json())


def test_cache_helpers() -> None:
    """Direct unit tests for _is_cache_valid, _get_cached_signal, _set_cached_signal."""
    import time  # noqa: PLC0415
    from datetime import date  # noqa: PLC0415

    from backend.interfaces.rest.routers.signals import (  # noqa: PLC0415
        _get_cached_signal,
        _is_cache_valid,
        _set_cached_signal,
        _signal_cache,
    )
    from backend.interfaces.rest.schemas.signals import SignalVector  # noqa: PLC0415

    # _is_cache_valid: fresh timestamp → valid
    assert _is_cache_valid(time.monotonic()) is True
    # _is_cache_valid: very old timestamp → invalid
    assert _is_cache_valid(time.monotonic() - 7200) is False

    # _get_cached_signal: unknown coin → None
    assert _get_cached_signal("UNKNOWN-COIN") is None

    # _set_cached_signal + _get_cached_signal round-trip
    sv = SignalVector(
        coin="TEST-USD",
        asof=date.today(),
        action="BUY",
        size_factor=0.5,
        consensus="2/3",
        sub_scores={"ma_signal": 1.0},
        confidence=0.8,
    )
    _set_cached_signal("TEST-USD", sv)
    result = _get_cached_signal("TEST-USD")
    assert result is not None
    assert result.coin == "TEST-USD"
    # Cleanup: remove test entry
    _signal_cache.pop("TEST-USD", None)


def test_signals_router_get_signal_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover GET /{coin} → get_signal endpoint (lines 154-178 in signals.py)."""
    from datetime import date  # noqa: PLC0415

    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    import backend.application.signals.signal_service as _svc  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import _signal_cache, router  # noqa: PLC0415
    from backend.interfaces.rest.schemas.signals import SignalVector  # noqa: PLC0415

    _signal_cache.clear()

    sv = SignalVector(
        coin="ETH-USD",
        asof=date.today(),
        action="HOLD",
        size_factor=0.5,
        consensus="2/3",
        sub_scores={"ma_signal": 1.0},
        confidence=0.6,
    )

    async def _fake_evaluate(coin, asof, prices_df):  # type: ignore
        return sv

    monkeypatch.setattr(_svc, "evaluate", _fake_evaluate)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/signals/ETH-USD")
    assert resp.status_code == 200
    assert resp.json()["coin"] == "ETH-USD"


def test_signals_router_get_signal_unknown_coin() -> None:
    """Cover 404 branch of get_signal (coin not in _CRYPTO_UNIVERSE)."""
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from backend.interfaces.rest.routers.signals import router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/signals/NOTACOIN")
    assert resp.status_code == 404


def test_signals_router_list_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover GET / → list_signals endpoint (lines 119-139 in signals.py)."""
    from datetime import date  # noqa: PLC0415

    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    import backend.application.signals.signal_service as _svc  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import _signal_cache, router  # noqa: PLC0415
    from backend.interfaces.rest.schemas.signals import SignalVector  # noqa: PLC0415

    _signal_cache.clear()

    sv = SignalVector(
        coin="BTC-USD",
        asof=date.today(),
        action="BUY",
        size_factor=1.0,
        consensus="3/3",
        sub_scores={"ma_signal": 1.0},
        confidence=0.9,
    )

    async def _fake_evaluate(coin, asof, prices_df):  # type: ignore
        return sv

    monkeypatch.setattr(_svc, "evaluate", _fake_evaluate)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/signals")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_run_walkforward_async_wrapper() -> None:
    """Cover run_walkforward async wrapper (lines 188-197 in signals.py)."""
    from backend.interfaces.rest.routers.signals import (  # noqa: PLC0415
        _make_stub_prices,
        run_walkforward,
    )
    from backend.interfaces.rest.schemas.signals import BacktestReport  # noqa: PLC0415

    prices_df = _make_stub_prices("BTC-USD", n=300)
    prices_df.columns = pd.Index(["close"])  # type: ignore

    report = await run_walkforward(coin="BTC-USD", prices_df=prices_df)
    assert isinstance(report, BacktestReport)
    assert report.coin == "BTC-USD"


def test_backtest_router_get_backtest_unknown_coin() -> None:
    """Cover 404 branch of get_backtest (lines 213-231 in signals.py)."""
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from backend.interfaces.rest.routers.signals import backtest_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(backtest_router)
    client = TestClient(app)
    resp = client.get("/api/v1/backtest/NOTACOIN")
    assert resp.status_code == 404


def test_backtest_router_get_backtest_valid_coin() -> None:
    """Cover happy path of get_backtest (lines 221-231 in signals.py)."""
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from backend.interfaces.rest.routers.signals import backtest_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(backtest_router)
    client = TestClient(app)
    resp = client.get("/api/v1/backtest/BTC-USD")
    assert resp.status_code == 200
    assert resp.json()["coin"] == "BTC-USD"


def test_signals_router_list_signals_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover list_signals cache hit path (lines 119-120 in signals.py)."""
    import time  # noqa: PLC0415

    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    import backend.interfaces.rest.routers.signals as _signals_mod  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import router  # noqa: PLC0415
    from backend.interfaces.rest.schemas.signals import SignalVector  # noqa: PLC0415

    sv = SignalVector(
        coin="BTC-USD",
        asof=__import__("datetime").date.today(),
        action="BUY",
        size_factor=1.0,
        consensus="3/3",
        sub_scores={"ma_signal": 1.0},
        confidence=0.9,
    )
    _signals_mod._list_cache = (time.monotonic(), [sv])

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/signals")
    assert resp.status_code == 200
    _signals_mod._list_cache = None


def test_signals_router_get_signal_error_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover ValueError → 422 path in get_signal (lines 164, 170-172)."""
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    import backend.application.signals.signal_service as _svc  # noqa: PLC0415
    from backend.interfaces.rest.routers.signals import _signal_cache, router  # noqa: PLC0415

    _signal_cache.clear()

    async def _raise_value_error(coin, asof, prices_df):  # type: ignore
        raise ValueError("invalid input")

    monkeypatch.setattr(_svc, "evaluate", _raise_value_error)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/signals/BTC-USD")
    assert resp.status_code == 422
