"""Pydantic-Schemas für den Rebalancing-Endpunkt."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RebalancingRequest(BaseModel):
    total_portfolio_value_chf: float = Field(gt=0, description="Gesamtportfoliowert in CHF")
    current_weights: dict[str, float] = Field(
        description="Ist-Gewichtung je Ticker (Summe sollte ~1.0 ergeben)"
    )
    target_weights: dict[str, float] = Field(
        description="Soll-Gewichtung je Ticker (Summe sollte ~1.0 ergeben)"
    )
    is_3a_account: bool = Field(
        default=False, description="Säule-3a-Konto mit BVV2-Einschränkungen"
    )
    transaction_cost_rate: float = Field(
        default=0.001, ge=0, le=0.05, description="Transaktionskostensatz pro Trade (default: 0.1%)"
    )


class RebalancingStepResponse(BaseModel):
    ticker: str
    action: Literal["BUY", "SELL", "HOLD"]
    current_weight: float
    target_weight: float
    delta_weight: float
    estimated_value_chf: float
    transaction_cost_chf: float
    is_3a_eligible: bool


class RebalancingPlanResponse(BaseModel):
    plan_id: UUID
    steps: list[RebalancingStepResponse]
    total_portfolio_value_chf: float
    total_transaction_cost_chf: float
    is_3a_account: bool
    computed_at: datetime
    disclaimer: str = (
        "Keine Anlageberatung. Historische Daten keine Garantie für zukünftige Ergebnisse."
    )
