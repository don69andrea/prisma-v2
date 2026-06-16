"""Pydantic-DTOs für InvestorProfile- und Discovery-Endpunkte."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Legacy: POST /api/v1/profile + GET /api/v1/discover
# ---------------------------------------------------------------------------


class InvestorProfileCreateRequest(BaseModel):
    session_id: str
    risk_profile: Literal["conservative", "moderate", "aggressive"]
    sector_affinity: list[str] = Field(default_factory=list)
    time_horizon: Literal["short", "medium", "long"] = "medium"
    investment_goal: Literal["housing", "retirement", "freedom", "beat_savings", "other"] = (
        "beat_savings"
    )
    profession: str | None = None
    known_tickers: list[str] = Field(default_factory=list)
    investment_amount: Literal["under_10k", "10k_100k", "over_100k"] = "10k_100k"
    esg_preference: Literal["yes", "no", "indifferent"] = "indifferent"
    income_preference: Literal["dividends", "growth", "balanced"] = "balanced"


class InvestorProfileResponse(BaseModel):
    session_id: str
    risk_profile: str
    sector_affinity: list[str]
    sector_hint: str | None = None
    time_horizon: str
    investment_goal: str
    investment_amount: str = "10k_100k"
    esg_preference: str = "indifferent"
    income_preference: str = "balanced"
    confidence_score: float
    onboarding_complete: bool


class DiscoveredStockResponse(BaseModel):
    ticker: str
    name: str
    sector: str | None
    market_cap_chf: Decimal | None
    exchange: str
    signal_reason: str = ""


class DiscoveryResponse(BaseModel):
    session_id: str
    total: int
    stocks: list[DiscoveredStockResponse]


# ---------------------------------------------------------------------------
# Conversational Discovery: POST /api/v1/discovery/session|answer|complete
# ---------------------------------------------------------------------------


class SessionResponse(BaseModel):
    session_id: str


class AnswerRequest(BaseModel):
    session_id: str
    turn: int = Field(ge=1, le=7)
    answer: str | list[str]
    brand_data: dict[str, dict[str, Any]] | None = None


class AnswerResponse(BaseModel):
    session_id: str
    next_turn: int | None
    confidence: float
    partial_profile: InvestorProfileResponse


class CompleteRequest(BaseModel):
    session_id: str


class CompleteResponse(BaseModel):
    profile: InvestorProfileResponse
    recommended_stocks: list[DiscoveredStockResponse]
