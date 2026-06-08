"""Domain Entity: DecisionAuditRecord — persistierter Entscheidungs-Audit-Trail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class DecisionAuditRecord:
    """Audit-Eintrag für eine BUY/HOLD/WATCH-Entscheidung.

    Enthält alle Komponenten-Scores und eine menschenlesbare Begründung.
    """

    id: UUID
    ticker: str
    signal: str
    weighted_score: float
    quant_score: float
    ml_score: float
    macro_score: float
    is_3a_eligible: bool
    snapshot_date: date
    computed_at: datetime
    explanation_de: str
