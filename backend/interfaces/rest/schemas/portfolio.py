"""Pydantic-Schemas für Portfolio Intelligence API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioAllocateRequest(BaseModel):
    """Request für die KI-Portfolio-Allokation aus einem bestehenden Ranking-Run.

    Hinweis: Erwartet ausschliesslich einen Verweis (`run_id`) auf einen bereits
    abgeschlossenen Ranking-Run — keine direkte Eingabe eigener Ticker/Stückzahlen.
    Für die Verwaltung eines eigenen Portfolios (Ist-/Soll-Gewichte) siehe
    `RebalancingRequest` (Endpoint: POST /api/v1/portfolio/rebalance).
    """

    run_id: UUID = Field(
        ...,
        description="ID eines bereits abgeschlossenen Ranking-Runs, dessen Top-Picks alloziert werden",
    )
    top_n: int = Field(
        default=10,
        ge=2,
        le=20,
        description="Anzahl der Top-Picks aus dem Ranking-Run, die berücksichtigt werden",
    )
    eligible_only: bool = Field(
        default=False,
        description="Nur BVV2/FINMA-Säule-3a-geeignete Titel aus dem Ranking-Run berücksichtigen",
    )
    method: str = Field(
        default="score_weighted",
        pattern="^(score_weighted|risk_parity|mean_variance)$",
        description=(
            "Allokationsmethode: score_weighted (proportional zum quant_score), "
            "risk_parity (umgekehrt proportional zur 30d-Volatilität) oder "
            "mean_variance (Markowitz Mean-Variance mit Ledoit-Wolf Shrinkage)"
        ),
    )


class PortfolioPositionResponse(BaseModel):
    ticker: str
    weight: float = Field(..., ge=0.0, le=1.0)
    quant_score: float
    is_3a_eligible: bool
    rationale_de: str


class PortfolioAllocationResponse(BaseModel):
    run_id: UUID
    method: str
    positions: list[PortfolioPositionResponse]
    overall_rationale_de: str
    computed_at: datetime
    eligible_only: bool
    total_positions: int
