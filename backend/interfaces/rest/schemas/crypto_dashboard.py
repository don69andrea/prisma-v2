"""Pydantic schemas for the V4-5 crypto dashboard endpoints.

Three endpoint contracts:
  GET  /api/v1/crypto/{coin}/agent-audit  → AgentAuditResponse
  GET  /api/v1/crypto/{coin}/ohlcv        → OHLCVResponse
  POST /api/v1/crypto/{coin}/confirm      → HitlConfirmResponse

All outputs are Pydantic-validated (no Any types, no free-text passthrough).
HITL confirm is a pure audit log — no auto-trading logic anywhere in this schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from backend.domain.schemas.agent_schemas import (
    BearCase,
    BullCase,
    MacroRegime,
    OnChainView,
    RiskVerdict,
    SentimentView,
    TechnicalView,
)


class AgentRunDetail(BaseModel):
    """Parsed content of agent_audit_trail.agent_run JSONB.

    All fields are Optional — the JSONB may have been produced by an older
    pipeline version that did not include all views.
    """

    technical: TechnicalView | None = None
    onchain: OnChainView | None = None
    sentiment: SentimentView | None = None
    macro: MacroRegime | None = None
    bull: BullCase | None = None
    bear: BearCase | None = None
    risk: RiskVerdict | None = None


class AgentAuditResponse(BaseModel):
    """Response for GET /api/v1/crypto/{coin}/agent-audit."""

    audit_trail_id: uuid.UUID
    coin: str
    asof: date
    agent_run: AgentRunDetail
    created_at: datetime


class OHLCVBar(BaseModel):
    """Single OHLCV candlestick bar."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVResponse(BaseModel):
    """Response for GET /api/v1/crypto/{coin}/ohlcv."""

    coin: str
    symbol: str  # e.g. "BTC-USD"
    bars: list[OHLCVBar]


class HitlConfirmRequest(BaseModel):
    """Request body for POST /api/v1/crypto/{coin}/confirm.

    IRON RULE: this only LOGS the decision. No auto-trading.
    SELL = cash/exposure 0, never short.
    """

    audit_trail_id: uuid.UUID
    decision: Literal["proceed", "abort"]


class HitlConfirmResponse(BaseModel):
    """Response for POST /api/v1/crypto/{coin}/confirm."""

    id: uuid.UUID
    audit_trail_id: uuid.UUID
    coin: str
    decision: Literal["proceed", "abort"]
    decided_at: datetime
