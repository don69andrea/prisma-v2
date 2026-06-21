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

from typing import Any

import numpy as np
import pandas as pd

from backend.application.signals.indicators import atr, macd, rsi

__all__ = [
    "_walkforward_meta_cv",
    "build_meta_features",
    "fit_meta_classifier",
    "predict_meta_label",
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
    vol_pred_col = (
        df["vol_pred"].shift(1) if "vol_pred" in df.columns else pd.Series(np.nan, index=df.index)
    )
    momentum_rank_col = (
        df["momentum_rank"].shift(1)
        if "momentum_rank" in df.columns
        else (pd.Series(np.nan, index=df.index))
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


# ── Wave B: Classifier + Walk-Forward ────────────────────────────────────────


def fit_meta_classifier(
    X: pd.DataFrame,
    y: pd.Series,
    model: str = "logreg",
) -> dict[str, Any]:
    """Fitte einen binären Meta-Classifier auf (X, y).

    Primär: LogisticRegression (L2, max_iter=1000, class_weight='balanced').
    Fallback: LGBMClassifier (nur wenn explizit model='lgbm' übergeben wird).

    Parameters
    ----------
    X:
        Feature-Matrix (bereits shift(1), keine NaN).
    y:
        Binäre Labels {0, 1}.
    model:
        'logreg' (Standard) oder 'lgbm'.

    Returns
    -------
    dict
        {model, model_type, feature_cols}
    """
    feature_cols = list(X.columns)

    if model == "lgbm":
        from lightgbm import LGBMClassifier  # noqa: PLC0415

        clf: object = LGBMClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            n_jobs=1,
            verbose=-1,
        )
        model_type = "lgbm"
    else:
        from sklearn.linear_model import LogisticRegression  # noqa: PLC0415

        clf = LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        )
        model_type = "logreg"

    # fit expects numpy arrays
    from sklearn.base import BaseEstimator  # noqa: PLC0415

    if not isinstance(clf, BaseEstimator):
        raise TypeError(f"Expected sklearn estimator, got {type(clf)}")
    clf.fit(X.values, y.values)

    return {"model": clf, "model_type": model_type, "feature_cols": feature_cols}


def _walkforward_meta_cv(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int = 252,
    step: int = 21,
    embargo: int = 5,
    model_type: str = "logreg",
) -> dict[str, Any]:
    """Expanding-Window Walk-Forward CV mit Embargo für den Meta-Classifier.

    Embargo-Regel: test_start = train_end + embargo. Dies verhindert
    Label-Leakage aus dem Triple-Barrier Forward-Horizon (5 Tage).

    No-Snooping-Garantie: Classifier wird NUR auf Trainings-Folds gefittet.
    OOS-Folds werden NIE während des Fits gesehen.

    Parameters
    ----------
    X:
        Feature-Matrix mit DatetimeIndex (shift(1) bereits angewendet).
    y:
        Binäre Labels {0, 1} mit gleichem Index wie X.
    min_train:
        Minimale Trainings-Grösse in Bars (Standard 252).
    step:
        Walk-Forward-Schrittweite in Bars (Standard 21).
    embargo:
        Embargo-Gap zwischen Train-Ende und Test-Start (Standard 5 Bars).
    model_type:
        'logreg' oder 'lgbm'.

    Returns
    -------
    dict
        {folds: list[dict], n_folds: int}
        Jedes Fold-Dict enthält: precision, recall, f1, n_trades_taken,
        n_trades_skipped, train_end_idx, test_start_idx.
    """
    from sklearn.metrics import f1_score, precision_score, recall_score  # noqa: PLC0415

    # Align X and y, drop NaN rows
    data = pd.concat([X, y.rename("__label__")], axis=1).dropna()
    n = len(data)

    fold_results: list[dict[str, Any]] = []

    # Expanding loop: train = data[:start], test = data[start+embargo : start+embargo+step]
    for start in range(min_train, n - step - embargo + 1, step):
        train = data.iloc[:start]
        test_start = start + embargo
        test_end = test_start + step
        if test_end > n:
            break
        test = data.iloc[test_start:test_end]

        X_train = train.drop(columns=["__label__"])
        y_train = train["__label__"]
        X_test = test.drop(columns=["__label__"])
        y_test = test["__label__"].values

        # Skip folds where train has < 2 classes (classifier cannot fit)
        if len(y_train.unique()) < 2:
            continue

        model_info = fit_meta_classifier(X_train, y_train, model=model_type)
        clf = model_info["model"]

        from sklearn.base import BaseEstimator  # noqa: PLC0415

        if not isinstance(clf, BaseEstimator):
            raise TypeError(f"Expected sklearn estimator, got {type(clf)}")
        y_pred = clf.predict(X_test.values)

        fold_results.append(
            {
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, zero_division=0)),
                "n_trades_taken": int(y_pred.sum()),
                "n_trades_skipped": int((y_pred == 0).sum()),
                "train_end_idx": int(start - 1),
                "test_start_idx": int(test_start),
            }
        )

    return {"folds": fold_results, "n_folds": len(fold_results)}


def predict_meta_label(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int = 252,
    step: int = 21,
    embargo: int = 5,
    model: str = "logreg",
) -> dict[str, Any]:
    """Walk-Forward Meta-Label Prediction mit aggregierten OOS-Metriken.

    Führt _walkforward_meta_cv durch, aggregiert Mean-Precision/-Recall
    und fitttet ein finales Modell auf allen Daten für Production-Scoring.

    Pitfall 6: Wenn n_folds < 10, wird finding='negative' mit Grund
    'insufficient_oos_folds' zurückgegeben — keine Metriken-Fabrikation.

    Parameters
    ----------
    X:
        Feature-Matrix (shift(1) bereits angewendet).
    y:
        Binäre Labels {0, 1}.
    min_train:
        Minimale Trainings-Grösse (Standard 252).
    step:
        Walk-Forward-Schrittweite (Standard 21).
    embargo:
        Embargo-Gap in Bars (Standard 5).
    model:
        'logreg' oder 'lgbm'.

    Returns
    -------
    dict
        {n_folds, mean_precision, mean_recall, mean_f1, final_model_info,
         folds, finding, finding_reason}
    """
    cv_result = _walkforward_meta_cv(
        X, y, min_train=min_train, step=step, embargo=embargo, model_type=model
    )

    n_folds = int(cv_result["n_folds"])
    folds: list[dict[str, Any]] = cv_result["folds"]

    if n_folds < 10:
        return {
            "n_folds": n_folds,
            "mean_precision": 0.0,
            "mean_recall": 0.0,
            "mean_f1": 0.0,
            "final_model_info": None,
            "folds": folds,
            "finding": "negative",
            "finding_reason": "insufficient_oos_folds",
        }

    mean_precision = float(np.mean([f["precision"] for f in folds]))
    mean_recall = float(np.mean([f["recall"] for f in folds]))
    mean_f1 = float(np.mean([f["f1"] for f in folds]))

    # Final model refit on all aligned data (for production scoring only)
    data_all = pd.concat([X, y.rename("__label__")], axis=1).dropna()
    X_all = data_all.drop(columns=["__label__"])
    y_all = data_all["__label__"]
    final_model_info = fit_meta_classifier(X_all, y_all, model=model)

    return {
        "n_folds": n_folds,
        "mean_precision": mean_precision,
        "mean_recall": mean_recall,
        "mean_f1": mean_f1,
        "final_model_info": final_model_info,
        "folds": folds,
        "finding": "positive" if mean_precision > 0.50 else "negative",
        "finding_reason": (
            "oos_precision_above_random"
            if mean_precision > 0.50
            else "oos_precision_at_or_below_random"
        ),
    }
