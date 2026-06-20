"""Application Service: Quantil-Prediction (C1-Contract, TEIL E §E1.4).

Lädt die 3 LightGBM-Quantil-Modelle und gibt QuantilePrediction zurück.
Feature-Mismatch wirft ValueError (Kap. 4.3).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from backend.application.services.ml_feature_service import (
    TEIL_F_FEATURE_COLS,
    _compute_bb_position,
    _compute_drawdown_12m,
    _compute_macd_hist,
    _compute_rsi,
    _macro_series_from_db,
    _price_to_52w_high_from_series,
    _return_nm_from_series,
    _step_value_on,
    _vol_30d_from_series,
    _vol_nd_from_series,
)
from backend.domain.value_objects.ml_prediction import QuantilePrediction

_logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
_FEATURE_HASH = hashlib.sha256(",".join(TEIL_F_FEATURE_COLS).encode()).hexdigest()[:8]

_model_cache: dict[str, Any] = {}


def _load_quantile_models() -> dict[str, Any]:
    global _model_cache
    if _model_cache:
        return _model_cache

    import joblib

    registry_path = _MODELS_DIR / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(
            "Keine Quantil-Modelle gefunden. Erst `scripts/train_quantile_model.py` ausführen."
        )

    reg = json.loads(registry_path.read_text())
    meta_file = reg.get("active_quantile")
    if not meta_file:
        raise FileNotFoundError("Kein aktives Quantil-Modell in registry.json")

    meta_path = _MODELS_DIR / meta_file
    meta = json.loads(meta_path.read_text())

    stored_hash = meta.get("feature_hash", "")
    if stored_hash and stored_hash != _FEATURE_HASH:
        raise ValueError(
            f"Feature-Mismatch: Modell feature_hash={stored_hash!r}, "
            f"Code feature_hash={_FEATURE_HASH!r}. Modell muss neu trainiert werden."
        )

    run_date = meta["trained_at"]
    models: dict[str, Any] = {}
    for qname in ("q10", "q50", "q90"):
        fname = f"quantile_{qname}_{run_date}.joblib"
        path = _MODELS_DIR / fname
        if not path.exists():
            raise FileNotFoundError(f"Modell-Datei fehlt: {path}")
        models[qname] = joblib.load(path)

    models["_meta"] = meta
    _model_cache = models
    _logger.info("Quantil-Modelle geladen (v%s, hash=%s)", run_date, _FEATURE_HASH)
    return models


class QuantilePredictionService:
    """Inferenz mit den 3 LightGBM-Quantil-Modellen."""

    async def predict(self, ticker: str, as_of: date | None = None) -> QuantilePrediction | None:
        """Gibt QuantilePrediction für (ticker, as_of) zurück.

        Liest Kurshistorie aus stock_price_history, Makro aus macro_rates.
        None wenn zu wenig Daten.
        """
        import pandas as pd
        from sqlalchemy import text

        from backend.infrastructure.persistence.session import get_session_factory

        target_date = as_of or date.today()
        ticker_upper = ticker.upper()

        factory = get_session_factory()
        async with factory() as sess:
            r = await sess.execute(
                text(
                    "SELECT date, close FROM stock_price_history "
                    "WHERE ticker = :t AND date <= :d ORDER BY date ASC"
                ),
                {"t": ticker_upper, "d": target_date},
            )
            rows = r.fetchall()
            smi_r = await sess.execute(
                text(
                    "SELECT date, close FROM stock_price_history "
                    "WHERE ticker = '^SSMI' AND date <= :d ORDER BY date ASC"
                ),
                {"d": target_date},
            )
            smi_rows = smi_r.fetchall()

        if len(rows) < 252 or len(smi_rows) < 63:
            _logger.warning("%s: zu wenig Kurshistorie für Quantil-Prediction", ticker_upper)
            return None

        idx = pd.to_datetime([row[0] for row in rows])
        close = pd.Series([float(row[1]) for row in rows], index=idx)
        smi_idx = pd.to_datetime([row[0] for row in smi_rows])
        smi_close = pd.Series([float(row[1]) for row in smi_rows], index=smi_idx)

        snb_series = await _macro_series_from_db("snb_policy")
        chf_eur_series = await _macro_series_from_db("chf_eur")
        inflation_series = await _macro_series_from_db("inflation_ch")

        smi_63 = _return_nm_from_series(smi_close, 63)
        mom_vs_smi_3m = _return_nm_from_series(close, 63) - smi_63

        features = {
            "return_1m": _return_nm_from_series(close, 21),
            "return_3m": _return_nm_from_series(close, 63),
            "return_6m": _return_nm_from_series(close, 126),
            "return_12m": _return_nm_from_series(close, 252),
            "vol_30d": _vol_30d_from_series(close),
            "vol_90d": _vol_nd_from_series(close, 90),
            "rsi_14": _compute_rsi(close),
            "price_to_52w_high": _price_to_52w_high_from_series(close),
            "momentum_vs_smi_3m": mom_vs_smi_3m,
            "bb_position": _compute_bb_position(close),
            "macd_hist": _compute_macd_hist(close),
            "drawdown_12m": _compute_drawdown_12m(close),
            "snb_rate": _step_value_on(snb_series, target_date, -0.75),
            "chf_eur": _step_value_on(chf_eur_series, target_date, 0.92),
            "inflation_ch": _step_value_on(inflation_series, target_date, 0.0),
        }

        x = np.array([[features[f] for f in TEIL_F_FEATURE_COLS]], dtype=np.float32)

        models = _load_quantile_models()
        meta = models["_meta"]

        raw_q10 = float(models["q10"].predict(x)[0])
        raw_q50 = float(models["q50"].predict(x)[0])
        raw_q90 = float(models["q90"].predict(x)[0])

        # Monotonie: q10 <= q50 <= q90
        q10, q50, q90 = tuple(float(v) for v in sorted([raw_q10, raw_q50, raw_q90]))

        from scripts.train_quantile_model import _prob_outperform

        prob = _prob_outperform(q10, q50, q90)

        return QuantilePrediction(
            ticker=ticker_upper,
            as_of=target_date,
            q10=round(q10, 6),
            q50=round(q50, 6),
            q90=round(q90, 6),
            prob_outperform=round(prob, 4),
            expected_edge=round(q50, 6),
            uncertainty=round(q90 - q10, 6),
            model_version=meta["trained_at"],
            feature_hash=_FEATURE_HASH,
        )
