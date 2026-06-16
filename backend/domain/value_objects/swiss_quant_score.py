"""Swiss Quant Score — Ergebnis des quantitativen Scorings für einen SMI-Titel."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SwissQuantScore:
    """Quantitatives Scoring-Ergebnis für einen Swiss Stock.

    Alle Scores sind im Bereich 0–100.
    Signal: BUY (composite >= 70) | HOLD (40–69) | SELL (< 40)
    """

    ticker: str
    value_score: float  # P/E + P/B gewichtet
    income_score: float  # Dividendenrendite
    quality_score: float  # EPS-Qualität
    composite: float  # Gesamtscore (gewichtetes Mittel)
    signal: str  # "BUY" | "HOLD" | "SELL"
    signal_reason: str = field(default="")
