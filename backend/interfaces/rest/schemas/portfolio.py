"""Pydantic-Schemas für Portfolio Intelligence API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioAllocateRequest(BaseModel):
    run_id: UUID
    top_n: int = Field(default=10, ge=2, le=20)
    eligible_only: bool = False
    method: str = Field(default="score_weighted", pattern="^(score_weighted|risk_parity)$")


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
