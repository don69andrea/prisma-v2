"""Pydantic-Schemas für Decision Intelligence API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DecisionSignalResponse(BaseModel):
    ticker: str
    snapshot_date: date
    signal: str = Field(..., description="BUY | HOLD | WATCH")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalisierter Weighted Score")
    weighted_score: float = Field(..., ge=0.0, le=100.0)
    quant_score: float = Field(..., ge=0.0, le=100.0)
    ml_score: float = Field(..., ge=0.0, le=100.0)
    macro_score: float = Field(..., ge=0.0, le=100.0)
    is_3a_eligible: bool


class DecisionListResponse(BaseModel):
    items: list[DecisionSignalResponse]
    total: int


class ExplainRequest(BaseModel):
    ticker: str
    signal: str
    confidence: float
    quant_score: float
    ml_score: float
    macro_score: float
    weighted_score: float


class ExplainResponse(BaseModel):
    ticker: str
    overall: str = Field(..., description="Warum dieses Signal?")
    quant_why: str = Field(..., description="Warum ist der Quant-Score so?")
    ml_why: str = Field(..., description="Warum ist der ML-Score so?")
    macro_why: str = Field(..., description="Warum ist der Makro-Score so?")
    risk_note: str = Field(..., description="Risikohinweis")
