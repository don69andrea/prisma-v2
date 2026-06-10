"""Tests für MLPrediction SHAP-Erweiterung."""

from datetime import date

import pytest

from backend.domain.value_objects.ml_prediction import MLPrediction, SHAPEntry

pytestmark = pytest.mark.unit


def test_shap_entry_fields() -> None:
    entry = SHAPEntry(
        feature="roe_zscore", shap_value=0.3, feature_value=1.2, label="Return on Equity"
    )
    assert entry.feature == "roe_zscore"
    assert entry.shap_value == 0.3
    assert entry.feature_value == 1.2
    assert entry.label == "Return on Equity"


def test_shap_entry_is_immutable() -> None:
    entry = SHAPEntry(
        feature="roe_zscore", shap_value=0.3, feature_value=1.2, label="Return on Equity"
    )
    with pytest.raises((AttributeError, TypeError)):
        entry.shap_value = 0.5  # type: ignore[misc]


def test_ml_prediction_has_shap_fields() -> None:
    pred = MLPrediction(
        ticker="NESN",
        snapshot_date=date(2026, 1, 1),
        predicted_class=2,
        signal="OUTPERFORM",
        prob_bottom=0.1,
        prob_mid=0.2,
        prob_top=0.7,
        confidence=0.7,
        model_type="xgboost",
        features={"roe_zscore": 1.2},
        shap_values=[
            SHAPEntry(
                feature="roe_zscore", shap_value=0.3, feature_value=1.2, label="Return on Equity"
            )
        ],
        shap_expected_value=0.1,
    )
    assert len(pred.shap_values) == 1
    assert pred.shap_expected_value == 0.1


def test_ml_prediction_shap_defaults_empty() -> None:
    pred = MLPrediction(
        ticker="NESN",
        snapshot_date=date(2026, 1, 1),
        predicted_class=2,
        signal="OUTPERFORM",
        prob_bottom=0.1,
        prob_mid=0.2,
        prob_top=0.7,
        confidence=0.7,
        model_type="xgboost",
        features={},
    )
    assert pred.shap_values == []
    assert pred.shap_expected_value == 0.0


def test_shap_values_not_shared_between_instances() -> None:
    pred_a = MLPrediction(
        ticker="NESN",
        snapshot_date=date(2026, 1, 1),
        predicted_class=2,
        signal="OUTPERFORM",
        prob_bottom=0.1,
        prob_mid=0.2,
        prob_top=0.7,
        confidence=0.7,
        model_type="xgboost",
        features={},
    )
    pred_b = MLPrediction(
        ticker="NOVN",
        snapshot_date=date(2026, 1, 1),
        predicted_class=1,
        signal="NEUTRAL",
        prob_bottom=0.2,
        prob_mid=0.6,
        prob_top=0.2,
        confidence=0.6,
        model_type="xgboost",
        features={},
    )
    assert pred_a.shap_values is not pred_b.shap_values
