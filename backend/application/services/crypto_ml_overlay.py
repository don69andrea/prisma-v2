"""CryptoMLOverlay — Risk-Gate für Krypto-Signale (PRISMA V3, TEIL G2).

Lädt das LightGBM-Modell aus models/crypto_v2_dir_2026-06-20.joblib und stellt
eine Gate-Funktion bereit: predict_proba(...) < GATE_THRESHOLD → Gefahrenzone.

WICHTIG: Das Modell ist ein RISIKO-OVERLAY, kein Return-Prädiktor.
- ml_score im kombinierten Gewichtungsschema bleibt 50 (neutral).
- Dieser Service blockiert Signale, wenn das Regime gefährlich ist (p < Schwelle).
- Kein Eingriff in die quant/macro-Gewichte.

Feature-Reihenfolge (13 Features, FEATURE_HASH = 03c3e1b0):
  return_1d, return_7d, return_30d, return_90d,
  vol_7d, vol_30d, rsi_14, bb_position, macd_hist,
  drawdown_90d, fear_greed, excess_vs_btc_30d, mvrv
"""

from __future__ import annotations

import hashlib
import logging
import warnings
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    import lightgbm as lgb

_log = logging.getLogger(__name__)

FEATURE_COLS = (
    "return_1d",
    "return_7d",
    "return_30d",
    "return_90d",
    "vol_7d",
    "vol_30d",
    "rsi_14",
    "bb_position",
    "macd_hist",
    "drawdown_90d",
    "fear_greed",
    "excess_vs_btc_30d",
    "mvrv",
)
_EXPECTED_HASH = hashlib.sha256(",".join(FEATURE_COLS).encode()).hexdigest()[:8]
_MODEL_FILENAME = "crypto_v2_dir_2026-06-20.joblib"

GATE_THRESHOLD = 0.35  # p < 0.35 → Gefahrenzone, Signal blockieren


class CryptoMLOverlay:
    """Lädt crypto-v2 Modell und bewertet Regime-Risiko pro Signal-Snapshot."""

    def __init__(self, models_dir: Path | None = None) -> None:
        if models_dir is None:
            models_dir = Path(__file__).resolve().parents[3] / "models"
        model_path = models_dir / _MODEL_FILENAME
        if not model_path.exists():
            raise FileNotFoundError(
                f"crypto-v2 Modell nicht gefunden: {model_path}\n"
                "Stelle sicher, dass feature/prisma-v3-phase-2-crypto-v2 gemergt ist "
                "oder die Datei aus diesem Branch extrahiert wurde."
            )
        import joblib

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model: lgb.LGBMClassifier = joblib.load(model_path)

        n_feat = getattr(self._model, "n_features_in_", None)
        if n_feat != 13:
            raise ValueError(
                f"Modell hat {n_feat} Features, erwartet 13 — falsches Modell geladen."
            )
        _log.info("CryptoMLOverlay geladen: %s (FEATURE_HASH=%s)", model_path.name, _EXPECTED_HASH)

    def predict_proba(
        self,
        close: pd.Series,
        btc_close: pd.Series,
        snap: pd.Timestamp,
        fear_greed: pd.Series,
        mvrv: pd.Series | None = None,
    ) -> float | None:
        """Gibt p(30d-Return > +2%) zurück, oder None bei zu wenig Daten."""
        features = _compute_features(close, btc_close, snap, fear_greed, mvrv)
        if features is None:
            return None
        X = np.array(features, dtype=np.float32).reshape(1, -1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return float(self._model.predict_proba(X)[0][1])

    def is_danger_zone(
        self,
        close: pd.Series,
        btc_close: pd.Series,
        snap: pd.Timestamp,
        fear_greed: pd.Series,
        mvrv: pd.Series | None = None,
        threshold: float = GATE_THRESHOLD,
    ) -> bool:
        """True wenn p < threshold → Signal blockieren. None → kein Blocking (kein Daten)."""
        p = self.predict_proba(close, btc_close, snap, fear_greed, mvrv)
        if p is None:
            return False  # Kein Daten → kein Blocking
        return p < threshold


# ---------------------------------------------------------------------------
# Feature-Berechnung (PIT-korrekt, exakt wie im Training)
# ---------------------------------------------------------------------------


def _rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).rolling(window).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(window).mean().iloc[-1]
    if loss == 0:
        return 100.0
    return float(100.0 - 100.0 / (1 + gain / loss))


def _bb_position(close: pd.Series, window: int = 20) -> float:
    if len(close) < window:
        return 0.5
    ma = close.rolling(window).mean().iloc[-1]
    std = close.rolling(window).std().iloc[-1]
    upper, lower = ma + 2 * std, ma - 2 * std
    if upper - lower < 1e-9:
        return 0.5
    return float(np.clip((close.iloc[-1] - lower) / (upper - lower), 0.0, 1.0))


def _macd_hist(close: pd.Series) -> float:
    if len(close) < 35:
        return 0.0
    ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
    macd_line = ema12 - ema26
    return float(macd_line - (macd_line * 0.9 + (ema12 - ema26) * 0.1))


def _drawdown(close: pd.Series, window: int = 90) -> float:
    tail = close.tail(window)
    peak = tail.max()
    if peak < 1e-9:
        return 0.0
    return float((close.iloc[-1] - peak) / peak)


def _step_lookup(series: pd.Series, snap_date: date, default: float = 0.0) -> float:
    if series is None or series.empty:
        return default
    idx = series.index
    before = [d for d in idx if d <= snap_date]
    return float(series[before[-1]]) if before else default


def _compute_features(
    close: pd.Series,
    btc_close: pd.Series,
    snap: pd.Timestamp,
    fear_greed: pd.Series,
    mvrv: pd.Series | None,
) -> list[float] | None:
    """Berechnet 13 Features PIT-korrekt (nur Daten ≤ snap). Exakt wie Training."""
    past = close[close.index <= snap]
    btc_past = btc_close[btc_close.index <= snap]
    if len(past) < 120:
        return None

    def ret(n: int) -> float:
        return float(past.iloc[-1] / past.iloc[-n] - 1) if len(past) > n else 0.0

    def vol(n: int) -> float:
        if len(past) < n + 1:
            return 0.0
        dr = past.tail(n + 1).pct_change().dropna()
        return float(dr.std() * np.sqrt(365))

    btc_ret30 = float(btc_past.iloc[-1] / btc_past.iloc[-30] - 1) if len(btc_past) > 30 else 0.0
    snap_date = snap.date() if hasattr(snap, "date") else snap
    fg_val = _step_lookup(fear_greed, snap_date, 50.0)
    mvrv_val = _step_lookup(mvrv, snap_date, 0.0) if mvrv is not None else 0.0

    return [
        ret(1),
        ret(7),
        ret(30),
        ret(90),
        vol(7),
        vol(30),
        _rsi(past.tail(60)),
        _bb_position(past.tail(30)),
        _macd_hist(past.tail(60)),
        _drawdown(past, 90),
        fg_val,
        ret(30) - btc_ret30,
        mvrv_val,
    ]
