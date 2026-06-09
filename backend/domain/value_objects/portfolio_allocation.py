"""Domain Value Objects: Portfolio-Allokation aus Top-N-Picks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PortfolioPosition:
    """Einzelne Position in der Portfolio-Allokation.

    weight: normalisiertes Gewicht (0.05–0.40), Summe über alle Positionen ≈ 1.0
    rationale_de: LLM-generierte Begründung, Pydantic-validiert
    """

    ticker: str
    weight: float
    quant_score: float
    is_3a_eligible: bool
    rationale_de: str


@dataclass(frozen=True)
class PortfolioAllocation:
    """Vollständige Portfolio-Allokation für einen Ranking-Run.

    method: "score_weighted" | "risk_parity"
    positions: nach Gewicht absteigend sortiert
    overall_rationale_de: LLM-generierte Gesamt-Begründung, Pydantic-validiert
    """

    run_id: UUID
    method: str
    positions: tuple[PortfolioPosition, ...]
    overall_rationale_de: str
    computed_at: datetime
    eligible_only: bool
