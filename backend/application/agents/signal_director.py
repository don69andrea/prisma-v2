"""SignalDirector — orchestration hub for the V4-3 Agentic Layer (D-01, D-07).

Runs the deterministic Signal Engine, 4 analyst agents in parallel
(asyncio.gather with return_exceptions=True for fallback resilience),
then Bull/Bear/Risk sequentially. Synthesizes a TradeSignal via pure
Python weighted combination. Persists all 8 agent outputs to the audit
trail (minority protection: both bull AND bear always stored).

D-06 compliance:
  - D-06 test 3 (Minority Protection): bear_case always in agent_run dict
  - D-06 test 4 (Fallback): analyst Exception → deterministic fallback + lowered confidence
  - D-06 test 6 (HITL Checkpoint): confidence < 0.65 → logging.warning once + disclaimer prefix

No-Shorting rule: RiskVerdict.max_size == 0.0 → TradeSignal.size_factor == 0.0.

asyncio.to_thread() for sync signal_service.evaluate (CLAUDE.md convention).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import Any, Literal

from backend.domain.schemas.agent_schemas import (
    BearCase,
    BullCase,
    MacroRegime,
    OnChainView,
    RiskVerdict,
    SentimentView,
    TechnicalView,
    TradeSignal,
)

_logger = logging.getLogger(__name__)

_LOW_CONFIDENCE_THRESHOLD = 0.65
_FALLBACK_CONFIDENCE_PENALTY = 0.15

# Weights for the weighted-confidence synthesis (must sum to 1.0)
_W_ENGINE = 0.30
_W_TECHNICAL = 0.15
_W_ONCHAIN = 0.15
_W_SENTIMENT = 0.10
_W_MACRO = 0.10
_W_BULL_BEAR = 0.10  # combined bull+bear contribution
_W_RISK = 0.10

_TRADE_DISCLAIMER = "Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."


# ---------------------------------------------------------------------------
# Deterministic fallback views (substituted when an analyst raises Exception)
# ---------------------------------------------------------------------------


def _fallback_technical(coin: str) -> TechnicalView:
    return TechnicalView(
        coin=coin,
        stance="NEUTRAL",
        consensus="0/3",
        key_signals=["[fallback: LLM unavailable]"],
        confidence=0.0,
        reasoning="Technical analyst unavailable — deterministic fallback applied.",
    )


def _fallback_onchain(coin: str) -> OnChainView:
    return OnChainView(
        coin=coin,
        valuation="FAIR",
        network_health="NEUTRAL",
        confidence=0.0,
        reasoning="On-chain analyst unavailable — deterministic fallback applied.",
    )


def _fallback_sentiment(coin: str) -> SentimentView:
    return SentimentView(
        coin=coin,
        score=0.0,
        regime="NEUTRAL",
        reasoning="Sentiment analyst unavailable — deterministic fallback applied.",
    )


def _fallback_macro() -> MacroRegime:
    return MacroRegime(
        regime="NEUTRAL",
        drivers=["[fallback: LLM unavailable]"],
        confidence=0.0,
        reasoning="Macro analyst unavailable — deterministic fallback applied.",
    )


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------


def _action_from_engine(engine_action: str) -> Literal["BUY", "HOLD", "SELL"]:
    """Map engine action to TradeSignal action (BUY/HOLD/SELL)."""
    if engine_action == "BUY":
        return "BUY"
    if engine_action == "SELL":
        return "SELL"
    return "HOLD"


def _synthesize(
    coin: str,
    tech: TechnicalView,
    onchain: OnChainView,
    senti: SentimentView,
    macro: MacroRegime,
    bull: BullCase,
    bear: BearCase,
    risk: RiskVerdict,
    engine_signal: Any,
    has_fallback: bool,
) -> TradeSignal:
    """Pure Python weighted synthesis — no LLM call.

    Returns a TradeSignal (without audit_trail_id; caller fills it in).
    confidence is a weighted combination of analyst confidences.
    size_factor is clamped to risk.max_size (no-shorting: 0.0 if max_size==0.0).
    """
    # Weighted confidence
    engine_conf: float = getattr(engine_signal, "confidence", 0.5)
    bull_bear_conf: float = 0.5  # BullCase/BearCase have no confidence field

    raw_confidence = (
        _W_ENGINE * engine_conf
        + _W_TECHNICAL * tech.confidence
        + _W_ONCHAIN * onchain.confidence
        + _W_SENTIMENT * 0.5  # SentimentView.score is -1..1, not a confidence
        + _W_MACRO * macro.confidence
        + _W_BULL_BEAR * bull_bear_conf
        + _W_RISK * (1.0 if risk.approve else 0.3)
    )

    if has_fallback:
        raw_confidence = max(0.0, raw_confidence - _FALLBACK_CONFIDENCE_PENALTY)

    confidence = min(1.0, max(0.0, raw_confidence))

    # Action mirrors engine action
    action = _action_from_engine(engine_signal.action)

    # D-06: Sentiment veto + downside-only size scaling (behind SENTIMENT_ENABLED flag)
    from backend.config import get_settings  # noqa: PLC0415 — imported here to avoid circular
    _settings = get_settings()

    if _settings.sentiment_enabled and senti.veto:
        action = "HOLD"  # Block BUY; SELL is never upgraded to BUY

    # No-shorting: clamp size_factor to risk.max_size
    base_size: float = getattr(engine_signal, "size_factor", 0.5)
    size_factor = min(base_size, risk.max_size)
    # Guarantee non-negative (schema enforces ge=0.0 but belt-and-suspenders)
    size_factor = max(0.0, size_factor)

    # D-06: Downside-only size scaling (after no-shorting clamp)
    if _settings.sentiment_enabled and senti.score < 0:
        size_factor = size_factor * (1 + senti.score * 0.3)
        size_factor = max(0.0, size_factor)  # belt-and-suspenders no-short

    # All 7 layer rationale keys
    rationale_by_layer: dict[str, str] = {
        "technical": tech.reasoning,
        "onchain": onchain.reasoning,
        "sentiment": senti.reasoning,
        "macro": macro.reasoning,
        "bull": bull.thesis,
        "bear": bear.thesis,
        "risk": risk.reasoning,
    }

    return TradeSignal(
        coin=coin,
        action=action,
        size_factor=size_factor,
        confidence=confidence,
        rationale_by_layer=rationale_by_layer,
        audit_trail_id=uuid.uuid4(),  # placeholder; overwritten after repo.insert
        disclaimer=_TRADE_DISCLAIMER,
    )


class SignalDirector:
    """Orchestration hub: engine → analysts (parallel) → bull/bear/risk → TradeSignal.

    Constructor injection of all dependencies (testable without DB/LLM).
    """

    def __init__(
        self,
        signal_service: Any,
        tech_agent: Any,
        onchain_agent: Any,
        senti_agent: Any,
        macro_agent: Any,
        bull_agent: Any,
        bear_agent: Any,
        risk_agent: Any,
        audit_repo: Any,
        prices_df: Any,
        onchain_df: Any | None = None,
        vol_model_info: dict[str, Any] | None = None,
    ) -> None:
        self._signal_service = signal_service
        self._tech_agent = tech_agent
        self._onchain_agent = onchain_agent
        self._senti_agent = senti_agent
        self._macro_agent = macro_agent
        self._bull_agent = bull_agent
        self._bear_agent = bear_agent
        self._risk_agent = risk_agent
        self._audit_repo = audit_repo
        self._prices_df = prices_df
        self._onchain_df = onchain_df
        self._vol_model_info = vol_model_info

    async def run(self, coin: str) -> TradeSignal:
        """Run the full D-01 pipeline and return an audited TradeSignal.

        Sequence:
          1. engine_signal via asyncio.to_thread (sync → async, CLAUDE.md rule)
          2. tech/onchain/senti/macro in parallel via asyncio.gather(return_exceptions=True)
          3. bull, bear, risk sequentially
          4. Python _synthesize (no LLM)
          5. HITL checkpoint if confidence < 0.65
          6. Persist all 8 outputs to audit trail; embed returned UUID
        """
        asof: date = date.today()

        # Step 1: deterministic engine signal (sync call wrapped in to_thread)
        engine_signal = await asyncio.to_thread(
            self._signal_service.evaluate,
            coin,
            asof,
            self._prices_df,
            self._onchain_df,
            self._vol_model_info,
        )

        # Step 2: 4 analysts in parallel, failures produce Exception objects
        _gather = await asyncio.gather(
            self._tech_agent.analyze(coin, getattr(engine_signal, "sub_scores", {})),
            self._onchain_agent.analyze(coin, {}),
            self._senti_agent.analyze(coin, {}),
            self._macro_agent.analyze(coin, {}),
            return_exceptions=True,
        )
        tech_raw: TechnicalView | BaseException = _gather[0]
        onchain_raw: OnChainView | BaseException = _gather[1]
        senti_raw: SentimentView | BaseException = _gather[2]
        macro_raw: MacroRegime | BaseException = _gather[3]

        # Fallback substitution for any failed analysts
        has_fallback = False

        if isinstance(tech_raw, BaseException):
            _logger.warning(
                "TechnicalAnalystAgent failed for %s: %s — using fallback", coin, tech_raw
            )
            tech: TechnicalView = _fallback_technical(coin)
            has_fallback = True
        else:
            tech = tech_raw

        if isinstance(onchain_raw, BaseException):
            _logger.warning(
                "OnChainAnalystAgent failed for %s: %s — using fallback", coin, onchain_raw
            )
            onchain: OnChainView = _fallback_onchain(coin)
            has_fallback = True
        else:
            onchain = onchain_raw

        if isinstance(senti_raw, BaseException):
            _logger.warning(
                "SentimentAnalystAgent failed for %s: %s — using fallback", coin, senti_raw
            )
            senti: SentimentView = _fallback_sentiment(coin)
            has_fallback = True
        else:
            senti = senti_raw

        if isinstance(macro_raw, BaseException):
            _logger.warning("MacroRegimeAgent failed for %s: %s — using fallback", coin, macro_raw)
            macro: MacroRegime = _fallback_macro()
            has_fallback = True
        else:
            macro = macro_raw

        # Step 3: Bull, Bear, Risk sequentially
        bull: BullCase = await self._bull_agent.build_case(coin, engine_signal)
        bear: BearCase = await self._bear_agent.build_case(coin, engine_signal)
        risk: RiskVerdict = await self._risk_agent.assess(coin, engine_signal)

        # Step 4: Python synthesis (pure deterministic, no LLM)
        signal = _synthesize(
            coin=coin,
            tech=tech,
            onchain=onchain,
            senti=senti,
            macro=macro,
            bull=bull,
            bear=bear,
            risk=risk,
            engine_signal=engine_signal,
            has_fallback=has_fallback,
        )

        # Step 5: HITL checkpoint — non-blocking (log + disclaimer, no UI block)
        if signal.confidence < _LOW_CONFIDENCE_THRESHOLD:
            _logger.warning(
                "LOW CONFIDENCE: %s confidence=%.3f below threshold %.2f — human review recommended",
                coin,
                signal.confidence,
                _LOW_CONFIDENCE_THRESHOLD,
            )
            signal = signal.model_copy(
                update={"disclaimer": f"LOW CONFIDENCE: {_TRADE_DISCLAIMER}"}
            )

        # Step 6: Persist ALL 8 outputs to audit trail (minority protection: bear always stored)
        agent_run: dict[str, Any] = {
            "tech_view": tech.model_dump(),
            "onchain_view": onchain.model_dump(),
            "senti_view": senti.model_dump(),
            "macro_regime": macro.model_dump(),
            "bull_case": bull.model_dump(),
            "bear_case": bear.model_dump(),  # minority protection: always included
            "risk_verdict": risk.model_dump(),
            "trade_signal": signal.model_dump(),
        }

        audit_id: uuid.UUID = await self._audit_repo.insert(coin, asof, agent_run)

        # Embed the REAL UUID returned by the repo (not the placeholder)
        final_signal = signal.model_copy(update={"audit_trail_id": audit_id})

        return final_signal
