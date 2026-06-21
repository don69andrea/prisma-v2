"""Layer 3 Vol-Forecast: HAR-Baseline + optionales LightGBM.

Walk-Forward-Validation:
  - Expanding Window (min_train=252 Tage), Schritt=21 Tage
  - Alle Features basieren auf shift(1) — kein Look-Ahead
  - realized_vol = rolling(5).std() × sqrt(252) — geglättete tägliche Vol
  - LightGBM NUR wenn OOS-R² strikt > HAR-OOS-R²

Funktionen:
  realized_vol(close, window=5)  → pd.Series  (annualisiert, geglättet)
  build_har_features(rv)          → pd.DataFrame (rv_1d, rv_5d, rv_22d)
  fit_walkforward(close, ...)     → dict[coin → model_info]
  predict_vol(close, model_info, asof_date) → float
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

_ANN_FACTOR = 252.0  # Annualisierungsfaktor (Handelstage)
_DEFAULT_STEP = 21  # Walk-Forward-Schritt (ca. 1 Monat — mehr OOS-Punkte)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def realized_vol(close: pd.Series, window: int = 5) -> pd.Series:
    """Berechne annualisierte realisierte Volatilität (rolling std).

    Parameters
    ----------
    close:
        Schlusskurs-Zeitreihe.
    window:
        Fenstergrösse für rolling std (Standard 5 Tage — Wochenvol).
        Liefert bessere Schätzungen als tägliche abs(log-return) da
        weniger Rauschen.

    Returns
    -------
    pd.Series
        Annualisierte Volatilität: rolling(window).std(log_returns) × √252.
        Erste ``window-1`` Werte sind NaN.
    """
    log_returns = np.log(close / close.shift(1))
    min_p = min(2, window)
    rv = log_returns.rolling(window, min_periods=min_p).std() * np.sqrt(_ANN_FACTOR)
    return rv


def build_har_features(rv: pd.Series) -> pd.DataFrame:
    """Erzeuge HAR-Feature-Matrix aus realisierter Vol-Zeitreihe.

    KRITISCH: Alle Features verwenden shift(1), um Look-Ahead zu verhindern.
    Feature rv_1d@t entspricht rv[t-1] (gestern), rv_5d@t = Ø rv[t-5..t-1], usw.

    Parameters
    ----------
    rv:
        Annualisierte tägliche realisierte Vol.

    Returns
    -------
    pd.DataFrame
        Spalten: rv_1d (shift 1), rv_5d (Ø letzte 5), rv_22d (Ø letzte 22).
    """
    rv_shifted = rv.shift(1)
    return pd.DataFrame(
        {
            "rv_1d": rv_shifted,
            "rv_5d": rv_shifted.rolling(5).mean(),
            "rv_22d": rv_shifted.rolling(22).mean(),
        },
        index=rv.index,
    )


def _oos_r2(y_true: np.ndarray[Any, Any], y_pred: np.ndarray[Any, Any], y_baseline: float) -> float:
    """OOS-R² gegenüber konstantem Baseline (Trainingsmittelwert)."""
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_base = float(np.sum((y_true - y_baseline) ** 2))
    if ss_base == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_base


def fit_walkforward(
    close: pd.DataFrame,
    min_train: int = 252,
    step: int = _DEFAULT_STEP,
) -> dict[str, dict[str, Any]]:
    """Walk-Forward-Fitting für alle Coins in ``close``.

    Für jeden Coin:
      1. Berechne realized_vol → HAR-Features → Target (rv.shift(-1))
      2. Expanding Window: Train bis t, OOS ab t+1 bis t+step
      3. Fit HAR (LinearRegression)
      4. Optional: fit LightGBM auf HAR-Features + vov_5d
         → Verwende LightGBM NUR wenn OOS-R² strikt > HAR-OOS-R²

    Parameters
    ----------
    close:
        DataFrame mit Coins als Spalten, Datum als Index.
    min_train:
        Minimale Trainingsgrösse (Handelstage).
    step:
        Schrittweite der Expanding-Window-Folds (Standard: 21 Tage).

    Returns
    -------
    dict
        {coin: {"model": fitted_model, "oos_r2": float,
                "model_type": "har"|"lgbm",
                "har_r2": float, "lgbm_r2": float|None,
                "feature_cols": list[str]}}
    """
    results: dict[str, dict[str, Any]] = {}

    for coin in close.columns:
        try:
            results[coin] = _fit_single_coin(close[coin], min_train=min_train, step=step)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vol-Forecast fit fehlgeschlagen für %s: %s", coin, exc)

    return results


def _fit_single_coin(
    price_series: pd.Series,
    min_train: int,
    step: int,
) -> dict[str, Any]:
    """Fit walk-forward für einen einzelnen Coin."""
    rv = realized_vol(price_series)
    features = build_har_features(rv)

    # Target: Vol des NÄCHSTEN Tages (forward-1, kein Look-Ahead im Training)
    target = rv.shift(-1)

    # Vol-of-Vol als zusätzliches LightGBM-Feature
    vov_5d = rv.rolling(5).std().shift(1)

    data = pd.concat(
        [features, vov_5d.rename("vov_5d"), target.rename("target")],
        axis=1,
    ).dropna()

    n = len(data)
    if n < min_train + step:
        # Nicht genug Daten: Fallback — HAR auf allen verfügbaren Daten
        X = data[["rv_1d", "rv_5d", "rv_22d"]].values
        y = data["target"].values
        if len(X) == 0:
            raise ValueError(f"Keine validen Datenpunkte nach dropna (n={len(price_series)})")
        model = LinearRegression().fit(X, y)
        return {
            "model": model,
            "oos_r2": 0.0,
            "model_type": "har",
            "har_r2": 0.0,
            "lgbm_r2": None,
            "feature_cols": ["rv_1d", "rv_5d", "rv_22d"],
        }

    # ── Walk-Forward Loop ─────────────────────────────────────────────────────
    har_preds: list[float] = []
    lgbm_preds: list[float] = []
    y_oos: list[float] = []
    train_means: list[float] = []

    for start in range(min_train, n - step + 1, step):
        train = data.iloc[:start]
        test = data.iloc[start : start + step]

        train_mean = float(train["target"].mean())
        train_means.extend([train_mean] * len(test))
        y_oos.extend(test["target"].tolist())

        # HAR (LinearRegression auf rv_1d, rv_5d, rv_22d)
        X_train = train[["rv_1d", "rv_5d", "rv_22d"]].values
        y_train = train["target"].values
        har_model = LinearRegression().fit(X_train, y_train)
        X_test = test[["rv_1d", "rv_5d", "rv_22d"]].values
        har_preds.extend(har_model.predict(X_test).tolist())

        # LightGBM (Versuch — mit vol_of_vol_5d als extra Feature)
        try:
            from lightgbm import LGBMRegressor  # noqa: PLC0415

            X_train_lgbm = train[["rv_1d", "rv_5d", "rv_22d", "vov_5d"]].values
            X_test_lgbm = test[["rv_1d", "rv_5d", "rv_22d", "vov_5d"]].values
            lgbm_model = LGBMRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                n_jobs=1,
                verbose=-1,
            )
            lgbm_model.fit(X_train_lgbm, y_train)
            lgbm_preds.extend(lgbm_model.predict(X_test_lgbm).tolist())
        except ImportError:
            lgbm_preds.extend([float("nan")] * len(test))

    y_arr = np.array(y_oos)
    har_arr = np.array(har_preds)
    # Baseline = Mittelwert der jeweiligen Trainings-Mittelwerte (rolling baseline)
    baseline_val = float(np.mean(train_means))

    har_r2 = _oos_r2(y_arr, har_arr, baseline_val)

    lgbm_r2: float | None = None
    use_lgbm = False
    lgbm_valid = bool(lgbm_preds) and not any(np.isnan(lgbm_preds))
    if lgbm_valid:
        lgbm_arr = np.array(lgbm_preds)
        lgbm_r2 = _oos_r2(y_arr, lgbm_arr, baseline_val)
        use_lgbm = lgbm_r2 > har_r2  # strikt besser

    # ── Final-Fit auf allen Daten mit Sieger-Modell ───────────────────────────
    if use_lgbm:
        from lightgbm import LGBMRegressor  # noqa: PLC0415

        final_model = LGBMRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            n_jobs=1,
            verbose=-1,
        )
        X_all = data[["rv_1d", "rv_5d", "rv_22d", "vov_5d"]].values
        final_model.fit(X_all, data["target"].values)
        model_type = "lgbm"
        feature_cols = ["rv_1d", "rv_5d", "rv_22d", "vov_5d"]
        oos_r2 = lgbm_r2
    else:
        X_all = data[["rv_1d", "rv_5d", "rv_22d"]].values
        final_model = LinearRegression().fit(X_all, data["target"].values)
        model_type = "har"
        feature_cols = ["rv_1d", "rv_5d", "rv_22d"]
        oos_r2 = har_r2

    return {
        "model": final_model,
        "oos_r2": float(oos_r2) if oos_r2 is not None else 0.0,
        "model_type": model_type,
        "har_r2": float(har_r2),
        "lgbm_r2": float(lgbm_r2) if lgbm_r2 is not None else None,
        "feature_cols": feature_cols,
    }


def predict_vol(
    close: pd.Series,
    model_info: dict[str, Any],
    asof_date: date,
) -> float:
    """Sage Vol für einen Coin zu einem bestimmten Datum vorher.

    Parameters
    ----------
    close:
        Vollständige Schlusskurs-Zeitreihe des Coins.
    model_info:
        Rückgabe von ``fit_walkforward`` für diesen Coin.
    asof_date:
        Datum, für das vorhergesagt werden soll.
        Nutzt nur Daten ≤ asof_date (kein Look-Ahead durch shift(1) in Features).

    Returns
    -------
    float
        Vorhergesagte annualisierte Vol, immer ≥ 0.01 (min-Clip).
    """
    rv = realized_vol(close)
    features = build_har_features(rv)
    vov_5d = rv.rolling(5).std().shift(1)

    asof_ts = pd.Timestamp(asof_date)
    features_filtered = features.loc[features.index <= asof_ts]
    vov_filtered = vov_5d.loc[vov_5d.index <= asof_ts]

    if features_filtered.empty:
        return 0.01

    last_features = features_filtered.iloc[-1]
    last_vov = (
        float(vov_filtered.iloc[-1])
        if not vov_filtered.empty and not np.isnan(float(vov_filtered.iloc[-1]))
        else 0.0
    )

    model = model_info["model"]
    feature_cols = model_info.get("feature_cols", ["rv_1d", "rv_5d", "rv_22d"])

    feature_map = {
        "rv_1d": float(last_features.get("rv_1d", 0.0)),
        "rv_5d": float(last_features.get("rv_5d", 0.0)),
        "rv_22d": float(last_features.get("rv_22d", 0.0)),
        "vov_5d": last_vov,
    }

    # Ersetze NaN durch 0.0 (defensiv)
    X = np.array(
        [
            [
                feature_map.get(c, 0.0) if not np.isnan(feature_map.get(c, 0.0)) else 0.0
                for c in feature_cols
            ]
        ]
    )

    pred = float(model.predict(X)[0])
    # Clip auf positiven Mindestwert — Volatilität ist immer > 0
    return float(np.clip(pred, 0.01, None))
