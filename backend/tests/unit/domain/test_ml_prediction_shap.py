"""Tests für MLPrediction SHAP-Erweiterung."""
import pytest
from backend.domain.value_objects.ml_prediction import MLPrediction, SHAPEntry
from datetime import date

pytestmark = pytest.mark.unit

def test_shap_entry_fields():
    entry = SHAPEntry(feature="roe_zscore", value=0.3, feature_value=1.2, label="Return on Equity")
    assert entry.feature == "roe_zscore"
    assert entry.value == 0.3

def test_ml_prediction_has_shap_fields():
    pred = MLPrediction(
        ticker="NESN", snapshot_date=date(2026,1,1), predicted_class=2, signal="OUTPERFORM",
        prob_bottom=0.1, prob_mid=0.2, prob_top=0.7, confidence=0.7, model_type="xgboost",
        features={"roe_zscore": 1.2},
        shap_values=[SHAPEntry(feature="roe_zscore", value=0.3, feature_value=1.2, label="Return on Equity")],
        shap_expected_value=0.1,
    )
    assert len(pred.shap_values) == 1
    assert pred.shap_expected_value == 0.1

def test_ml_prediction_shap_defaults_empty():
    pred = MLPrediction(
        ticker="NESN", snapshot_date=date(2026,1,1), predicted_class=2, signal="OUTPERFORM",
        prob_bottom=0.1, prob_mid=0.2, prob_top=0.7, confidence=0.7, model_type="xgboost", features={},
    )
    assert pred.shap_values == []
    assert pred.shap_expected_value == 0.0
