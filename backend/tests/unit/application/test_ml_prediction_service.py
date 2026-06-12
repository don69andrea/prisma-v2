"""Unit-Tests für MLPredictionService."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.application.services.ml_prediction_service import MLPredictionService
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector
from backend.domain.value_objects.ml_prediction import MLPrediction, SHAPEntry


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
        return_6m=0.06,
        return_3m=0.03,
        vol_30d=0.18,
        vol_90d=0.20,
        rsi_14=55.0,
        price_to_52w_high=0.92,
        vol_trend=1.05,
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

    with (
        patch(
            "backend.application.services.ml_prediction_service._load_model",
            return_value=(model, "xgboost"),
        ),
        patch(
            "backend.application.services.ml_prediction_service._build_shap_entries",
            return_value=([], 0.0),
        ),
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

    with (
        patch(
            "backend.application.services.ml_prediction_service._load_model",
            return_value=(model, "lightgbm"),
        ),
        patch(
            "backend.application.services.ml_prediction_service._build_shap_entries",
            return_value=([], 0.0),
        ),
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


# --- SHAP Tests ---


def _make_shap_explainer_mock(shap_matrix: list[list[float]]) -> MagicMock:
    import numpy as np

    explainer = MagicMock()
    explainer.shap_values.return_value = [
        np.zeros_like(shap_matrix),
        np.zeros_like(shap_matrix),
        np.array(shap_matrix),
    ]
    explainer.expected_value = [0.05, 0.1, 0.15]
    return explainer


def test_build_shap_entries_top8_sorted() -> None:
    """_build_shap_entries gibt Top-8 Entries sortiert nach |shap_value| zurück."""
    import numpy as np

    from backend.application.services.ml_prediction_service import _build_shap_entries

    fv = _make_feature_vector()
    feature_names = list(fv.FEATURE_NAMES)
    features_dict = fv.to_feature_dict()
    n = len(feature_names)

    # Build mock model with mock explainer
    model = MagicMock()
    # SHAP values: first feature gets largest value, rest get smaller values
    shap_row = np.zeros(n)
    shap_row[0] = 0.5  # largest
    shap_row[1] = -0.3  # second
    shap_row[2] = 0.1  # third
    # rest are 0

    explainer = MagicMock()
    explainer.shap_values.return_value = [
        np.zeros((1, n)),
        np.zeros((1, n)),
        shap_row.reshape(1, n),
    ]
    explainer.expected_value = [0.05, 0.1, 0.15]

    with patch("shap.TreeExplainer", return_value=explainer):
        entries, expected = _build_shap_entries(
            model, np.zeros((1, n)), feature_names, features_dict, 2
        )

    assert expected == pytest.approx(0.15)
    assert len(entries) <= 8
    # First entry has largest abs value
    assert abs(entries[0].shap_value) >= abs(entries[1].shap_value)
    assert entries[0].shap_value == pytest.approx(0.5)


def test_build_shap_entries_returns_empty_on_exception() -> None:
    """_build_shap_entries gibt leere Liste zurück wenn SHAP fehlschlägt."""
    import numpy as np

    from backend.application.services.ml_prediction_service import _build_shap_entries

    model = MagicMock()
    with patch("shap.TreeExplainer", side_effect=RuntimeError("SHAP failed")):
        entries, expected = _build_shap_entries(model, np.zeros((1, 5)), ["f1"], {"f1": 0.5}, 2)

    assert entries == []
    assert expected == 0.0


@pytest.mark.asyncio
async def test_predict_includes_shap_values() -> None:
    """predict() gibt shap_values zurück wenn Modell XGBoost ist."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()
    model = _make_mock_model(predicted_class=2)

    with (
        patch(
            "backend.application.services.ml_prediction_service._load_model",
            return_value=(model, "xgboost"),
        ),
        patch(
            "backend.application.services.ml_prediction_service._build_shap_entries",
            return_value=(
                [SHAPEntry("roe_zscore", 0.3, 1.2, "Return on Equity")],
                0.15,
            ),
        ),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert result is not None
    assert len(result.shap_values) == 1
    assert result.shap_values[0].feature == "roe_zscore"
    assert result.shap_expected_value == 0.15


@pytest.mark.asyncio
async def test_predict_shap_empty_on_non_xgboost() -> None:
    """Bei model_type != xgboost/lightgbm: shap_values bleibt leer."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()
    model = _make_mock_model(predicted_class=1)

    with patch(
        "backend.application.services.ml_prediction_service._load_model",
        return_value=(model, "unknown"),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert result is not None
    assert result.shap_values == []
    assert result.shap_expected_value == 0.0
