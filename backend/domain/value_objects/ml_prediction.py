"""Domain Value Object: ML Prediction — Ergebnis des Return-Predictor-Modells."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar


@dataclass(frozen=True)
class MLPrediction:
    """Vorhersage des Return-Predictor-Modells für einen Ticker.

    predicted_class: 0=Bottom, 1=Mid, 2=Top Quartil (12M-Forward-Return)
    signal: "UNDERPERFORM" | "NEUTRAL" | "OUTPERFORM"
    probabilities: Wahrscheinlichkeit je Klasse (0–1, Summe ≈ 1)
    confidence: max(probabilities) als Konfidenz-Maß
    """

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

    _CLASS_TO_SIGNAL: ClassVar[dict[int, str]] = {0: "UNDERPERFORM", 1: "NEUTRAL", 2: "OUTPERFORM"}

    @classmethod
    def signal_for_class(cls, predicted_class: int) -> str:
        return cls._CLASS_TO_SIGNAL.get(predicted_class, "NEUTRAL")
