"""Domain Value Object: ML Prediction — Ergebnis des Return-Predictor-Modells."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar

@dataclass(frozen=True)
class SHAPEntry:
    feature: str
    value: float
    feature_value: float
    label: str

@dataclass(frozen=True)
class MLPrediction:
    ticker: str
    snapshot_date: date
    predicted_class: int
    signal: str
    prob_bottom: float
    prob_mid: float
    prob_top: float
    confidence: float
    model_type: str
    features: dict[str, float]
    shap_values: list[SHAPEntry] = field(default_factory=list)
    shap_expected_value: float = 0.0

    _CLASS_TO_SIGNAL: ClassVar[dict[int, str]] = {0: "UNDERPERFORM", 1: "NEUTRAL", 2: "OUTPERFORM"}

    @classmethod
    def signal_for_class(cls, predicted_class: int) -> str:
        return cls._CLASS_TO_SIGNAL.get(predicted_class, "NEUTRAL")
