"""Domain Value Objects für Cost-Tracking-Summary.

Diese Dataclasses sind reine Datenstrukturen ohne Verhalten — sie
beschreiben das Vokabular, in dem Application und Interfaces über
Kosten reden. Persistence- und Framework-frei.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §9.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ModelBreakdown:
    model: str
    calls: int
    cost_usd: Decimal


@dataclass(frozen=True)
class FeatureBreakdown:
    feature: str
    calls: int
    cost_usd: Decimal


@dataclass(frozen=True)
class CallEntry:
    created_at: datetime
    model: str
    feature: str
    cost_usd: Decimal


@dataclass(frozen=True)
class CostBreakdown:
    """Aggregat-Result aus dem Persistence-Layer für den aktuellen Monat.

    Enthält keine Cap-Information — die ergänzt der Service.
    """

    by_model: list[ModelBreakdown]
    by_feature: list[FeatureBreakdown]
    last_calls: list[CallEntry]


@dataclass(frozen=True)
class CostSummary:
    """Service-Output: Cap-Status + Aggregate für den aktuellen Monat (UTC)."""

    month: str  # "YYYY-MM"
    cap_usd: Decimal
    current_usd: Decimal
    remaining_usd: Decimal  # max(cap - current, 0)
    by_model: list[ModelBreakdown]
    by_feature: list[FeatureBreakdown]
    last_calls: list[CallEntry]
