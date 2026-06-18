"""Pydantic-Schemas für Multi-Agent Director, Checkpoints und Reports."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisStep(BaseModel):
    agent: str
    status: Literal["running", "done", "error"]
    result: str | None = None


class DirectorEvent(BaseModel):
    type: Literal["step", "checkpoint", "done", "error"]
    agent: str | None = None
    status: Literal["running", "done", "error", "planning"] | None = None
    result: str | None = None
    checkpoint_id: str | None = None
    message: str | None = None
    options: list[str] = Field(default_factory=list)
    run_id: str | None = None
    signal: str | None = None
    confidence: float | None = None
    report: dict[str, Any] | None = None
    error: str | None = None


class MacroToolReport(BaseModel):
    ticker: str
    score: float = Field(ge=0.0, le=100.0)
    leitzins: float
    chf_eur: float
    climate: str
    chf_impact: Literal["POSITIV", "NEUTRAL", "NEGATIV"]
    reasoning: str


class CointelligenceReport(BaseModel):
    coin: Literal["BTC", "ETH"]
    price_chf: float
    mvrv_zone: Literal["UNDERBOUGHT", "FAIR", "EXPENSIVE", "EXTREME", "UNKNOWN"]
    fear_greed: int = Field(ge=0, le=100)
    sharpe_crypto: float
    sharpe_smi: float
    chf_usd_impact: Literal["GÜNSTIG", "NEUTRAL", "UNGÜNSTIG"]
    regime_signal: Literal["ACCUMULATE", "HOLD", "CAUTION", "AVOID"]
    max_allocation_pct: float = Field(ge=0.0, le=10.0)
    reasoning: str = Field(min_length=10)
    disclaimer: str


class CheckpointAnswer(BaseModel):
    answer: str
