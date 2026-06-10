"""Application Service: ML Prediction — lädt Modell und gibt Vorhersage zurück."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from backend.application.services.ml_feature_service import MLFeatureService
from backend.domain.value_objects.ml_prediction import MLPrediction, SHAPEntry

_logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
_LATEST_MODEL = _MODELS_DIR / "return_predictor_latest.joblib"
_LATEST_META = _MODELS_DIR / "return_predictor_latest.json"

_model_cache: Any = None
_model_type_cache: str = "unknown"

_FEATURE_LABELS: dict[str, str] = {
    "quant_score": "Quant-Gesamtscore",
    "score_rendite": "Score Rendite",
    "score_sicherheit": "Score Sicherheit",
    "score_wachstum": "Score Wachstum",
    "score_substanz": "Score Substanz",
    "return_12m": "12M Return",
    "vol_30d": "30-Tage Volatilität",
    "rsi_14": "RSI (14)",
    "snb_rate": "SNB Leitzins",
    "chf_eur": "CHF/EUR Kurs",
}
_TOP_N_SHAP = 8


def _load_model() -> tuple[Any, str]:
    global _model_cache, _model_type_cache
    if _model_cache is not None:
        return _model_cache, _model_type_cache

    import joblib

    if not _LATEST_MODEL.exists():
        raise FileNotFoundError(
            f"Kein trainiertes Modell gefunden unter {_LATEST_MODEL}. "
            "Bitte zuerst `python scripts/train_return_predictor.py` ausführen."
        )

    _model_cache = joblib.load(_LATEST_MODEL)
    _model_type_cache = "unknown"

    import json

    if _LATEST_META.exists():
        with _LATEST_META.open() as f:
            meta = json.load(f)
        _model_type_cache = meta.get("model_type", "unknown")

    _logger.info("Return-Predictor geladen: %s (%s)", _LATEST_MODEL.name, _model_type_cache)
    return _model_cache, _model_type_cache


def _build_shap_entries(
    model: Any,
    x: np.ndarray,
    feature_names: list[str],
    features_dict: dict[str, float],
    predicted_class: int,
) -> tuple[list[SHAPEntry], float]:
    """Berechnet SHAP-Werte für den predicted_class und gibt Top-N zurück.

    Gibt leere Liste zurück wenn SHAP-Berechnung fehlschlägt.
    """
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        raw = explainer.shap_values(x)

        if isinstance(raw, list) and len(raw) > predicted_class:
            class_shap = raw[predicted_class][0]
            expected_value = float(
                explainer.expected_value[predicted_class]
                if hasattr(explainer.expected_value, "__len__")
                else explainer.expected_value
            )
        else:
            class_shap = np.array(raw).flatten()
            expected_value = float(
                explainer.expected_value
                if not hasattr(explainer.expected_value, "__len__")
                else explainer.expected_value[0]
            )

        indexed = sorted(enumerate(class_shap), key=lambda t: abs(t[1]), reverse=True)[:_TOP_N_SHAP]

        entries = [
            SHAPEntry(
                feature=feature_names[i],
                shap_value=round(float(v), 4),
                feature_value=round(features_dict.get(feature_names[i], 0.0), 4),
                label=_FEATURE_LABELS.get(feature_names[i], feature_names[i]),
            )
            for i, v in indexed
        ]
        return entries, round(expected_value, 4)

    except Exception:
        _logger.warning("SHAP-Berechnung fehlgeschlagen — wird übersprungen", exc_info=True)
        return [], 0.0


class MLPredictionService:
    """Führt Inferenz mit dem Return-Predictor-Modell durch."""

    def __init__(self, feature_service: MLFeatureService | None = None) -> None:
        self._feature_service = feature_service or MLFeatureService()

    async def predict(self, ticker: str) -> MLPrediction | None:
        """Gibt eine ML-Vorhersage mit SHAP-Erklärung zurück.

        Returns None wenn Features nicht verfügbar.
        Raises FileNotFoundError wenn kein Modell vorhanden.
        """
        feature_vector = await self._feature_service.build_features(ticker)
        if feature_vector is None:
            return None

        model, model_type = _load_model()
        features_dict = feature_vector.to_feature_dict()
        feature_names = list(feature_vector.FEATURE_NAMES)
        x = np.array([[features_dict[n] for n in feature_names]], dtype=np.float32)

        pred_class = int(model.predict(x)[0])
        try:
            probas = model.predict_proba(x)[0]
            prob_bottom = float(probas[0])
            prob_mid = float(probas[1])
            prob_top = float(probas[2])
        except (AttributeError, IndexError):
            prob_bottom = 1.0 if pred_class == 0 else 0.0
            prob_mid = 1.0 if pred_class == 1 else 0.0
            prob_top = 1.0 if pred_class == 2 else 0.0

        confidence = max(prob_bottom, prob_mid, prob_top)

        if model_type in ("xgboost", "lightgbm"):
            shap_entries, shap_expected = _build_shap_entries(
                model, x, feature_names, features_dict, pred_class
            )
        else:
            shap_entries, shap_expected = [], 0.0

        return MLPrediction(
            ticker=ticker.upper(),
            snapshot_date=date.today(),
            predicted_class=pred_class,
            signal=MLPrediction.signal_for_class(pred_class),
            prob_bottom=round(prob_bottom, 4),
            prob_mid=round(prob_mid, 4),
            prob_top=round(prob_top, 4),
            confidence=round(confidence, 4),
            model_type=model_type,
            features=features_dict,
            shap_values=shap_entries,
            shap_expected_value=shap_expected,
        )
