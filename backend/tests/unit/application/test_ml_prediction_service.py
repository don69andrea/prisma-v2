"""Unit-Tests für MLPredictionService."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.application.services.ml_prediction_service import MLPredictionService
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector
from backend.domain.value_objects.ml_prediction import MLPrediction


def _make_feature_vector(ticker: str = "NESN") -> MLFeatureVector:
    return MLFeatureVector(
        ticker=ticker,
        snapshot_date=date(2024, 6, 1),
        quant_score=65.0,
        score_rendite=55.0,
        score_sicherheit=70.0,
        score_wachstum=60.0,
        score_substanz=60.0,
        return_12m=0.12,
        vol_30d=0.18,
        rsi_14=55.0,
        snb_rate=0.25,
        chf_eur=0.93,
        forward_return_12m=None,
        target_class=None,
    )


def _make_mock_model(predicted_class: int = 2) -> MagicMock:
    model = MagicMock()
    model.predict.return_value = np.array([predicted_class])
    probas = [0.1, 0.2, 0.7] if predicted_class == 2 else [0.6, 0.3, 0.1]
    model.predict_proba.return_value = np.array([probas])
    return model


@pytest.mark.asyncio
async def test_predict_returns_outperform() -> None:
    """Top-Quartil-Vorhersage → signal=OUTPERFORM, confidence hoch."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()
    model = _make_mock_model(predicted_class=2)

    with patch(
        "backend.application.services.ml_prediction_service._load_model",
        return_value=(model, "xgboost"),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert isinstance(result, MLPrediction)
    assert result.ticker == "NESN"
    assert result.predicted_class == 2
    assert result.signal == "OUTPERFORM"
    assert result.prob_top == 0.7
    assert result.confidence == 0.7
    assert result.model_type == "xgboost"
    assert len(result.features) == 10


@pytest.mark.asyncio
async def test_predict_returns_underperform() -> None:
    """Bottom-Quartil-Vorhersage → signal=UNDERPERFORM."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()
    model = _make_mock_model(predicted_class=0)

    with patch(
        "backend.application.services.ml_prediction_service._load_model",
        return_value=(model, "lightgbm"),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert result is not None
    assert result.predicted_class == 0
    assert result.signal == "UNDERPERFORM"
    assert result.model_type == "lightgbm"


@pytest.mark.asyncio
async def test_predict_returns_none_when_no_features() -> None:
    """Keine Marktdaten → None zurückgeben."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = None

    service = MLPredictionService(feature_service=feature_svc)
    result = await service.predict("UNKNOWN")
    assert result is None


@pytest.mark.asyncio
async def test_predict_raises_when_no_model() -> None:
    """Kein Modell-Artifact → FileNotFoundError."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()

    with patch(
        "backend.application.services.ml_prediction_service._load_model",
        side_effect=FileNotFoundError("kein Modell"),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        with pytest.raises(FileNotFoundError):
            await service.predict("NESN")


@pytest.mark.asyncio
async def test_predict_without_predict_proba() -> None:
    """Modell ohne predict_proba → Fallback-Probabilities."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()

    model = MagicMock()
    model.predict.return_value = np.array([1])
    model.predict_proba.side_effect = AttributeError("no predict_proba")

    with patch(
        "backend.application.services.ml_prediction_service._load_model",
        return_value=(model, "xgboost"),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert result is not None
    assert result.predicted_class == 1
    assert result.signal == "NEUTRAL"
    assert result.prob_mid == 1.0
    assert result.prob_bottom == 0.0
    assert result.prob_top == 0.0


def test_signal_for_class() -> None:
    assert MLPrediction.signal_for_class(0) == "UNDERPERFORM"
    assert MLPrediction.signal_for_class(1) == "NEUTRAL"
    assert MLPrediction.signal_for_class(2) == "OUTPERFORM"
    assert MLPrediction.signal_for_class(99) == "NEUTRAL"
