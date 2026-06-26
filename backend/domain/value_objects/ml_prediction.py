"""Domain Value Object: ML Prediction — Ergebnis des Return-Predictor-Modells."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar


@dataclass(frozen=True)
class SHAPEntry:
    """Ein Feature-Beitrag aus SHAP TreeExplainer.

    shap_value: SHAP-Wert (positiv = Richtung OUTPERFORM, negativ = Richtung UNDERPERFORM)
    feature_value: Roher Feature-Wert (z.B. 0.18 für ROE)
    label: Human-readable Name für UI-Anzeige
    """

    feature: str
    shap_value: float
    feature_value: float
    label: str


@dataclass(frozen=True)
class MLPrediction:
    """Vorhersage des Return-Predictor-Modells für einen Ticker.

    predicted_class: 0=Bottom, 1=Mid, 2=Top Quartil (12M-Forward-Return)
    signal: "UNDERPERFORM" | "NEUTRAL" | "OUTPERFORM"
    probabilities: Wahrscheinlichkeit je Klasse (0–1, Summe ≈ 1)
    confidence: max(probabilities) als Konfidenz-Maß
    shap_values: Top-8 Feature-Contributions sortiert nach |shap_value|
    shap_expected_value: Modell-Baseline (Durchschnitt über Trainingsdaten)
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
    shap_values: list[SHAPEntry] = field(default_factory=list)
    shap_expected_value: float = 0.0

    _CLASS_TO_SIGNAL: ClassVar[dict[int, str]] = {0: "UNDERPERFORM", 1: "NEUTRAL", 2: "OUTPERFORM"}

    @classmethod
    def signal_for_class(cls, predicted_class: int) -> str:
        return cls._CLASS_TO_SIGNAL.get(predicted_class, "NEUTRAL")


@dataclass(frozen=True)
class QuantilePrediction:
    """C1-Contract: Quantil-Regression des 30-Tage-Excess-Return vs SMI (TEIL E §E1).

    q10/q50/q90: 10%/50%/90%-Quantil des erwarteten Excess-Return (z.B. -0.04 = -4%).
    prob_outperform: P(excess > 0), lineare CDF-Interpolation aus (q10, q50, q90).
    expected_edge: = q50 (Convenience-Alias).
    uncertainty: = q90 - q10 (Spread als Risiko-Proxy).
    feature_hash: sha256[:8] der feature_cols-Liste — erkennt Feature-Mismatch.
    """

    ticker: str
    as_of: date
    q10: float
    q50: float
    q90: float
    prob_outperform: float
    expected_edge: float
    uncertainty: float
    model_version: str
    feature_hash: str
