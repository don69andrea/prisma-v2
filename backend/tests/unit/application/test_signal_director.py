"""Unit-Tests für SignalDirector (D-01 synthesis, D-06 tests 3, 4, 6).

TDD: Tests written BEFORE implementation exists (RED → fail on ImportError).

D-06 mandatory tests covered here:
  - D-06 test 3: Minority protection — bear_case always in agent_run dict
  - D-06 test 4: Fallback resilience — analyst Exception → TradeSignal still returned
  - D-06 test 6: HITL checkpoint — confidence < 0.65 → exactly one logging.warning call

Additional tests:
  - synthesis: rationale_by_layer has all 7 keys
  - no-shorting: RiskVerdict.max_size 0.0 → size_factor 0.0
  - audit trail: repo.insert called once; UUID in TradeSignal.audit_trail_id
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

AUDIT_UUID = uuid.uuid4()
COIN = "BTC"
ASOF = date(2026, 1, 1)


def _make_signal_vector(action: str = "BUY", size_factor: float = 0.8, confidence: float = 0.75) -> MagicMock:
    sv = MagicMock()
    sv.coin = COIN
    sv.asof = ASOF
    sv.action = action
    sv.size_factor = size_factor
    sv.confidence = confidence
    sv.sub_scores = {"ma_signal": 1.0, "macd_signal": 1.0, "rsi_signal": 1.0}
    return sv


def _make_technical_view(confidence: float = 0.8) -> TechnicalView:
    return TechnicalView(
        coin=COIN,
        stance="BULLISH",
        consensus="3/3",
        key_signals=["MA above 200"],
        confidence=confidence,
        reasoning="Strong momentum.",
    )


def _make_onchain_view(confidence: float = 0.7) -> OnChainView:
    return OnChainView(
        coin=COIN,
        valuation="FAIR",
        network_health="STRONG",
        confidence=confidence,
        reasoning="Healthy network.",
    )


def _make_sentiment_view() -> SentimentView:
    return SentimentView(
        coin=COIN,
        score=0.3,
        regime="GREED",
        reasoning="Markets greedy.",
    )


def _make_macro_regime(confidence: float = 0.7) -> MacroRegime:
    return MacroRegime(
        regime="RISK_ON",
        drivers=["Low rates"],
        confidence=confidence,
        reasoning="Risk on environment.",
    )


def _make_bull_case() -> BullCase:
    return BullCase(
        thesis="BTC will moon.",
        strongest_points=["Institutional adoption"],
        risks_acknowledged=["Regulatory risk"],
    )


def _make_bear_case() -> BearCase:
    return BearCase(
        thesis="BTC will dump.",
        strongest_points=["High leverage"],
        counter_to_bull=["Weak on-chain"],
    )


def _make_risk_verdict(approve: bool = True, max_size: float = 0.8) -> RiskVerdict:
    return RiskVerdict(
        approve=approve,
        max_size=max_size,
        breaches=[],
        reasoning="Within limits.",
    )


def _make_director(
    engine_signal=None,
    tech_view=None,
    onchain_view=None,
    senti_view=None,
    macro_regime=None,
    bull_case=None,
    bear_case=None,
    risk_verdict=None,
    audit_uuid=None,
):
    """Build a SignalDirector with all dependencies mocked."""
    from backend.application.agents.signal_director import SignalDirector

    if engine_signal is None:
        engine_signal = _make_signal_vector()
    if tech_view is None:
        tech_view = _make_technical_view()
    if onchain_view is None:
        onchain_view = _make_onchain_view()
    if senti_view is None:
        senti_view = _make_sentiment_view()
    if macro_regime is None:
        macro_regime = _make_macro_regime()
    if bull_case is None:
        bull_case = _make_bull_case()
    if bear_case is None:
        bear_case = _make_bear_case()
    if risk_verdict is None:
        risk_verdict = _make_risk_verdict()
    if audit_uuid is None:
        audit_uuid = AUDIT_UUID

    signal_service = MagicMock()
    signal_service.evaluate = MagicMock(return_value=engine_signal)

    tech_agent = MagicMock()
    tech_agent.analyze = AsyncMock(return_value=tech_view)

    onchain_agent = MagicMock()
    onchain_agent.analyze = AsyncMock(return_value=onchain_view)

    senti_agent = MagicMock()
    senti_agent.analyze = AsyncMock(return_value=senti_view)

    macro_agent = MagicMock()
    macro_agent.analyze = AsyncMock(return_value=macro_regime)

    bull_agent = MagicMock()
    bull_agent.build_case = AsyncMock(return_value=bull_case)

    bear_agent = MagicMock()
    bear_agent.build_case = AsyncMock(return_value=bear_case)

    risk_agent = MagicMock()
    risk_agent.assess = AsyncMock(return_value=risk_verdict)

    audit_repo = MagicMock()
    audit_repo.insert = AsyncMock(return_value=audit_uuid)

    director = SignalDirector(
        signal_service=signal_service,
        tech_agent=tech_agent,
        onchain_agent=onchain_agent,
        senti_agent=senti_agent,
        macro_agent=macro_agent,
        bull_agent=bull_agent,
        bear_agent=bear_agent,
        risk_agent=risk_agent,
        audit_repo=audit_repo,
        prices_df=MagicMock(),
        onchain_df=None,
        vol_model_info=None,
    )
    return director, audit_repo


# ---------------------------------------------------------------------------
# Task 1 Tests: synthesis, run, no-shorting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_valid_trade_signal():
    """run(coin) returns a valid TradeSignal whose audit_trail_id == mocked UUID."""
    director, audit_repo = _make_director()

    result = await director.run(COIN)

    assert isinstance(result, TradeSignal)
    assert result.coin == COIN
    assert result.action in ("BUY", "HOLD", "SELL")
    assert result.audit_trail_id == AUDIT_UUID


@pytest.mark.asyncio
async def test_synthesis_rationale_by_layer_has_all_7_keys():
    """rationale_by_layer must contain all 7 layer keys."""
    director, _ = _make_director()

    result = await director.run(COIN)

    expected_keys = {"technical", "onchain", "sentiment", "macro", "bull", "bear", "risk"}
    assert expected_keys == set(result.rationale_by_layer.keys()), (
        f"Missing keys: {expected_keys - set(result.rationale_by_layer.keys())}"
    )


@pytest.mark.asyncio
async def test_no_shorting_max_size_zero_propagates_to_size_factor():
    """RiskVerdict.max_size == 0.0 → TradeSignal.size_factor == 0.0 (no-shorting rule)."""
    risk_verdict = _make_risk_verdict(approve=False, max_size=0.0)
    director, _ = _make_director(risk_verdict=risk_verdict)

    result = await director.run(COIN)

    assert result.size_factor == 0.0


@pytest.mark.asyncio
async def test_audit_trail_id_is_real_uuid_from_repo():
    """repo.insert called exactly once; returned UUID embedded in TradeSignal."""
    custom_uuid = uuid.uuid4()
    director, audit_repo = _make_director(audit_uuid=custom_uuid)

    result = await director.run(COIN)

    audit_repo.insert.assert_called_once()
    assert result.audit_trail_id == custom_uuid


# ---------------------------------------------------------------------------
# Task 2 Tests: fallback, checkpoint, minority protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_analyst_exception_still_returns_trade_signal():
    """D-06 test 4: analyst raises Exception → run() still returns a TradeSignal, confidence lowered."""
    from backend.application.agents.signal_director import SignalDirector

    engine_signal = _make_signal_vector(confidence=0.75)
    signal_service = MagicMock()
    signal_service.evaluate = MagicMock(return_value=engine_signal)

    # tech_agent raises Exception
    tech_agent = MagicMock()
    tech_agent.analyze = AsyncMock(side_effect=Exception("LLM timeout"))

    onchain_agent = MagicMock()
    onchain_agent.analyze = AsyncMock(return_value=_make_onchain_view())

    senti_agent = MagicMock()
    senti_agent.analyze = AsyncMock(return_value=_make_sentiment_view())

    macro_agent = MagicMock()
    macro_agent.analyze = AsyncMock(return_value=_make_macro_regime())

    bull_agent = MagicMock()
    bull_agent.build_case = AsyncMock(return_value=_make_bull_case())

    bear_agent = MagicMock()
    bear_agent.build_case = AsyncMock(return_value=_make_bear_case())

    risk_agent = MagicMock()
    risk_agent.assess = AsyncMock(return_value=_make_risk_verdict())

    audit_repo = MagicMock()
    audit_repo.insert = AsyncMock(return_value=AUDIT_UUID)

    director = SignalDirector(
        signal_service=signal_service,
        tech_agent=tech_agent,
        onchain_agent=onchain_agent,
        senti_agent=senti_agent,
        macro_agent=macro_agent,
        bull_agent=bull_agent,
        bear_agent=bear_agent,
        risk_agent=risk_agent,
        audit_repo=audit_repo,
        prices_df=MagicMock(),
        onchain_df=None,
        vol_model_info=None,
    )

    result = await director.run(COIN)

    assert isinstance(result, TradeSignal)
    # Confidence must be lowered due to fallback
    assert result.confidence < 0.75


@pytest.mark.asyncio
async def test_checkpoint_low_confidence_triggers_exactly_one_warning():
    """D-06 test 6: confidence < 0.65 → exactly 1 logging.warning + disclaimer prefix."""
    # Force very low confidences
    tech_view = _make_technical_view(confidence=0.4)
    onchain_view = _make_onchain_view(confidence=0.4)
    macro_regime = _make_macro_regime(confidence=0.4)
    engine_signal = _make_signal_vector(confidence=0.4)

    director, _ = _make_director(
        engine_signal=engine_signal,
        tech_view=tech_view,
        onchain_view=onchain_view,
        macro_regime=macro_regime,
    )

    with patch("backend.application.agents.signal_director._logger") as mock_logger:
        result = await director.run(COIN)

    assert result.confidence < 0.65
    assert mock_logger.warning.call_count == 1
    assert result.disclaimer.startswith("LOW CONFIDENCE:")


@pytest.mark.asyncio
async def test_minority_protection_bear_case_always_in_agent_run():
    """D-06 test 3: bear_case key must be in agent_run dict passed to repo.insert."""
    director, audit_repo = _make_director()

    await director.run(COIN)

    audit_repo.insert.assert_called_once()
    call_args = audit_repo.insert.call_args
    # positional: (coin, asof, agent_run)
    agent_run_dict = call_args[0][2]

    assert "bear_case" in agent_run_dict, "bear_case must always be persisted (minority protection)"


@pytest.mark.asyncio
async def test_all_8_outputs_in_agent_run():
    """repo.insert agent_run contains all 8 expected keys."""
    director, audit_repo = _make_director()

    await director.run(COIN)

    call_args = audit_repo.insert.call_args
    agent_run_dict = call_args[0][2]

    expected_keys = {
        "tech_view", "onchain_view", "senti_view", "macro_regime",
        "bull_case", "bear_case", "risk_verdict", "trade_signal",
    }
    assert expected_keys == set(agent_run_dict.keys()), (
        f"Missing keys: {expected_keys - set(agent_run_dict.keys())}"
    )


@pytest.mark.asyncio
async def test_repo_insert_called_once_per_run():
    """repo.insert is called exactly once per run() invocation."""
    director, audit_repo = _make_director()

    await director.run(COIN)

    audit_repo.insert.assert_called_once()
