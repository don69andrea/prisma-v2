"""Unit-Tests für Layer 3 Vol-Forecast: HAR-Baseline + optional LightGBM.

Alle Tests gemäss Plan A7.4:
- OOS-R² > 0 auf synthetischen Daten für ≥ 2 Coins
- LightGBM NUR wenn OOS-R² > HAR-Baseline
- Kein Look-Ahead (shift(1) erzwungen)
- pred_vol immer positiv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── Lazy import — schlägt fehl (RED) bis Implementierung existiert ──────────
def _import() -> tuple:  # type: ignore[type-arg]
    from backend.application.signals.vol_forecast import (  # noqa: PLC0415
        build_har_features,
        fit_walkforward,
        predict_vol,
        realized_vol,
    )

    return realized_vol, build_har_features, fit_walkforward, predict_vol


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _synthetic_close(
    n: int = 400,
    drift: float = 0.0002,
    vol: float = 0.02,
    seed: int = 42,
) -> pd.Series:
    """Synthetische Log-Normal-Preisreihe."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, vol, n)
    prices = 100.0 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.Series(prices, index=idx, name="COIN")


def _synthetic_close_df(n: int = 400) -> pd.DataFrame:
    """DataFrame mit 2 synthetischen Preisreihen."""
    return pd.DataFrame(
        {
            "BTC": _synthetic_close(n=n, vol=0.03, seed=1),
            "ETH": _synthetic_close(n=n, vol=0.025, seed=2),
        }
    )


# ── Tests: realized_vol ───────────────────────────────────────────────────────


def test_realized_vol_positive():
    """realized_vol muss immer > 0 sein (nach Dropna)."""
    realized_vol, *_ = _import()
    close = _synthetic_close()
    rv = realized_vol(close)
    rv_clean = rv.dropna()
    assert len(rv_clean) > 0
    assert (rv_clean > 0).all(), "realized_vol enthält Werte ≤ 0"


def test_realized_vol_annualized():
    """Tägliche Vol × √252 → annualisierte Zahl > 0 (window=5 Standard)."""
    realized_vol, *_ = _import()
    close = _synthetic_close(vol=0.02)
    rv = realized_vol(close)  # Standard window=5
    assert rv.dropna().mean() > 0.0


# ── Tests: build_har_features ────────────────────────────────────────────────


def test_har_features_no_lookahead():
    """Alle HAR-Features müssen shift(1) haben → Feature@t benutzt Daten ≤ t-1."""
    realized_vol, build_har_features, *_ = _import()
    close = _synthetic_close()
    rv = realized_vol(close)
    features = build_har_features(rv)

    # Prüfe: rv_1d an Index t = rv.shift(1) an t → rv[t-1]
    rv_shifted = rv.shift(1)
    # Vergleiche alignierten Anteil (nach Dropna)
    common = features["rv_1d"].dropna().index.intersection(rv_shifted.dropna().index)
    pd.testing.assert_series_equal(
        features["rv_1d"].loc[common],
        rv_shifted.loc[common],
        check_names=False,
        atol=1e-12,
    )


def test_har_features_columns():
    """HAR-Features müssen Spalten rv_1d, rv_5d, rv_22d enthalten."""
    realized_vol, build_har_features, *_ = _import()
    close = _synthetic_close()
    rv = realized_vol(close)
    features = build_har_features(rv)
    assert "rv_1d" in features.columns
    assert "rv_5d" in features.columns
    assert "rv_22d" in features.columns


# ── Tests: fit_walkforward ────────────────────────────────────────────────────


def test_har_oos_r2_positive():
    """HAR OOS-R² > 0 auf einer synthetischen Vol-Reihe (≥ 300 Bars)."""
    _, _, fit_walkforward, _ = _import()
    close = _synthetic_close_df(n=400)
    results = fit_walkforward(close, min_train=252)

    assert "BTC" in results
    assert results["BTC"]["oos_r2"] > 0.0, (
        f"HAR OOS-R² = {results['BTC']['oos_r2']:.4f} — erwartet > 0"
    )


def test_vol_forecast_two_coins_oos_positive():
    """A7.4: OOS-R² > 0 auf ≥ 2 verschiedenen synthetischen Coins."""
    _, _, fit_walkforward, _ = _import()
    close = _synthetic_close_df(n=400)
    results = fit_walkforward(close, min_train=252)

    for coin in ["BTC", "ETH"]:
        assert coin in results
        r2 = results[coin]["oos_r2"]
        assert r2 > 0.0, f"{coin}: OOS-R² = {r2:.4f} — erwartet > 0"


def test_lgbm_only_when_better_than_har():
    """LightGBM darf nur verwendet werden, wenn OOS-R² > HAR-OOS-R²."""
    _, _, fit_walkforward, _ = _import()
    # Mit kurzer Reihe: LightGBM wird wahrscheinlich NICHT besser als HAR
    close = _synthetic_close_df(n=400)
    results = fit_walkforward(close, min_train=252)

    for coin, info in results.items():
        model_type = info["model_type"]
        # Wenn LGBM gewählt: LGBM-R² muss > HAR-R² gewesen sein
        if model_type == "lgbm":
            assert info.get("lgbm_r2", float("-inf")) > info.get("har_r2", float("inf")), (
                f"{coin}: LGBM gewählt obwohl LGBM-R² nicht > HAR-R²"
            )


def test_model_type_is_valid_string():
    """model_type muss 'har' oder 'lgbm' sein."""
    _, _, fit_walkforward, _ = _import()
    close = _synthetic_close_df(n=400)
    results = fit_walkforward(close, min_train=252)
    for coin, info in results.items():
        assert info["model_type"] in {"har", "lgbm"}, (
            f"{coin}: unbekannter model_type={info['model_type']!r}"
        )


# ── Tests: predict_vol ───────────────────────────────────────────────────────


def test_predict_vol_positive():
    """predict_vol() muss immer > 0 liefern (nie NaN, nie 0)."""
    realized_vol, _, fit_walkforward, predict_vol = _import()
    close = _synthetic_close_df(n=400)
    results = fit_walkforward(close, min_train=252)

    # Für BTC vorhersagen
    btc_series = close["BTC"]
    model_info = results["BTC"]
    pred = predict_vol(btc_series, model_info, asof_date=date(2022, 3, 1))
    assert pred > 0.0, f"predict_vol hat {pred} zurückgegeben"
    assert not np.isnan(pred)


def test_predict_vol_clipped_minimum():
    """pred_vol darf nicht unter 0.01 fallen (min-Clip gemäss Spec)."""
    realized_vol, _, fit_walkforward, predict_vol = _import()
    close = _synthetic_close_df(n=400)
    results = fit_walkforward(close, min_train=252)

    btc_series = close["BTC"]
    model_info = results["BTC"]
    pred = predict_vol(btc_series, model_info, asof_date=date(2022, 3, 1))
    assert pred >= 0.01
