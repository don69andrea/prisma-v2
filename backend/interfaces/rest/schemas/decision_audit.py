"""Pydantic-Schemas für Decision Audit Trail API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DecisionAuditRecordResponse(BaseModel):
    id: UUID
    ticker: str
    signal: str = Field(..., description="BUY | HOLD | SELL")
    weighted_score: float
    quant_score: float
    ml_score: float
    macro_score: float
    is_3a_eligible: bool
    snapshot_date: date
    computed_at: datetime
    explanation_de: str


class DecisionAuditListResponse(BaseModel):
    ticker: str
    records: list[DecisionAuditRecordResponse]
    total: int


class DecisionAuditComputeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
