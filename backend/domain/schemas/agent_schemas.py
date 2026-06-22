"""Pydantic output schemas for all agent types in the V4-3 Agentic Layer.

Single source of truth for the 8 D-05 agent output contracts (see 03-CONTEXT.md).
Every downstream agent, the SignalDirector, the audit-trail repository, and the
REST endpoint MUST use these schemas.

Design rules (enforced by tests):
  - All classes subclass pydantic.BaseModel
  - All bounded floats use Field(ge=..., le=...)
  - All enum fields use typing.Literal (no freetext can pass through)
  - No __post_init__, no computation — pure data contracts only
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "TechnicalView",
    "OnChainView",
    "SentimentView",
    "MacroRegime",
    "BullCase",
    "BearCase",
    "RiskVerdict",
    "TradeSignal",
]

_TRADE_DISCLAIMER = "Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."


class TechnicalView(BaseModel):
    """Output of TechnicalAnalystAgent — reads indicator state from Signal Engine."""

    coin: str
    stance: Literal["BULLISH", "NEUTRAL", "BEARISH"]
    consensus: str  # e.g. "3/3", "2/3"
    key_signals: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str  # <= 3 sentences


class OnChainView(BaseModel):
    """Output of OnChainAnalystAgent — reads MVRV-Z / network health from Tools."""

    coin: str
    valuation: Literal["CHEAP", "FAIR", "EXPENSIVE"]
    network_health: Literal["STRONG", "NEUTRAL", "WEAK"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SentimentView(BaseModel):
    """Output of SentimentAnalystAgent — Fear&Greed from market_sentiment table.

    news_surprise is None in stub (V4-4 fills via RAG).
    veto defaults False (no veto in stub).
    sources defaults [] (RAG pending V4-4).
    """

    coin: str
    score: float = Field(ge=-1.0, le=1.0)  # (fg_value - 50) / 50
    regime: Literal["FEAR", "NEUTRAL", "GREED"]
    news_surprise: bool | None = None
    veto: bool = False
    reasoning: str
    sources: list[str] = []


class MacroRegime(BaseModel):
    """Output of MacroRegimeAgent (crypto-focused, cache 1h TTL)."""

    regime: Literal["RISK_ON", "NEUTRAL", "RISK_OFF"]
    drivers: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str  # <= 2 sentences


class BullCase(BaseModel):
    """Output of BullResearchAgent — deliberately one-sided bullish thesis."""

    thesis: str
    strongest_points: list[str]
    risks_acknowledged: list[str]


class BearCase(BaseModel):
    """Output of BearResearchAgent — deliberately one-sided bearish thesis."""

    thesis: str
    strongest_points: list[str]
    counter_to_bull: list[str]


class RiskVerdict(BaseModel):
    """Output of RiskAgent — veto/cap decision on position sizing."""

    approve: bool
    max_size: float = Field(ge=0.0, le=1.5)
    breaches: list[str]
    reasoning: str


class TradeSignal(BaseModel):
    """Final synthesized signal from SignalDirector.

    SELL means cash (exposure 0) — NEVER short, NEVER negative size_factor.
    audit_trail_id references the agent_audit_trail DB row (UUID, required).
    rationale_by_layer maps layer names to reasoning strings.
    """

    coin: str
    action: Literal["BUY", "HOLD", "SELL"]
    size_factor: float = Field(ge=0.0, le=1.5)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_by_layer: dict[str, str]  # {"technical": ..., "onchain": ..., ...}
    audit_trail_id: uuid.UUID
    disclaimer: str = _TRADE_DISCLAIMER
