"""Domain Value Object: Decision Signal — aggregiertes BUY/HOLD/SELL-Signal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar


@dataclass(frozen=True)
class DecisionSignal:
    """Aggregiertes Handelssignal aus Quant + ML + Macro.

    signal: "BUY" | "HOLD" | "SELL"
    confidence: 0.0–1.0 (normalisierter weighted_score / 100)
    component_scores: Komponenten-Beiträge (0–100 je)
    is_3a_eligible: Säule-3a-Eignung
    """

    ticker: str
    snapshot_date: date
    signal: str
    confidence: float
    weighted_score: float
    quant_score: float
    ml_score: float
    macro_score: float
    is_3a_eligible: bool

    _SIGNAL_THRESHOLDS: ClassVar[dict[str, tuple[float, float]]] = {
        "BUY": (65.0, 100.0),
        "HOLD": (40.0, 65.0),
        "SELL": (0.0, 40.0),
    }

    @classmethod
    def signal_for_score(cls, weighted_score: float) -> str:
        if weighted_score >= 65.0:
            return "BUY"
        if weighted_score >= 40.0:
            return "HOLD"
        return "SELL"
