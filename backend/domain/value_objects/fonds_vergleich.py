"""FondsVergleich Value Object — Vergleich VIAC-Fonds vs. Einzeltitel-Portfolio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ViacFonds:
    """Statische VIAC-Fondsdaten aus Factsheets (Stand 2024)."""

    name: str
    description: str
    equity_ratio: float
    expected_return_pa: Decimal
    volatility_pa: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal


@dataclass(frozen=True)
class PortfolioCompareMetrics:
    """Berechnete Kennzahlen für ein Portfolio."""

    expected_return_pa: Decimal
    volatility_pa: Decimal
    sharpe_ratio: Decimal | None
    max_drawdown: Decimal


@dataclass(frozen=True)
class FondsVergleich:
    """Vergleichsergebnis VIAC-Fonds vs. Custom-Portfolio."""

    fonds_name: str
    fonds_metrics: PortfolioCompareMetrics
    custom_metrics: PortfolioCompareMetrics
    snapshot_date: date
    disclaimer: str = (
        "Historische Performance ≠ Zukunft. "
        "Diese Analyse dient ausschliesslich zu Bildungszwecken — keine Anlageberatung."
    )
