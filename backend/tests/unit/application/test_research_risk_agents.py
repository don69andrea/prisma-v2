"""Unit-Tests für BullResearchAgent, BearResearchAgent, RiskAgent.

D-06 mandatory tests (§6 AGENTS.md):
  - D-06 test 1: Hallucination guard (covered by tool_choice assertion)
  - D-06 test 2: State-from-Tool (RiskAgent reads exposure from Store, not LLM memory)
  - D-06 test 7: No-Shorting (SELL → max_size == 0.0, never negative)

TDD: Tests written BEFORE implementations exist (RED → fail on ImportError).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_tool_use_block(tool_name: str, data: dict[str, Any]) -> MagicMock:
    """Create a mock Anthropic content block simulating a tool_use response."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = data
    return block


def _make_text_block(text: str = "Some text") -> MagicMock:
    """Create a mock Anthropic content block simulating a text response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_llm_response(*blocks: MagicMock) -> MagicMock:
    """Create a mock Anthropic messages response with given content blocks."""
    response = MagicMock()
    response.content = list(blocks)
    return response


def _make_signal(action: str = "BUY", size_factor: float = 1.0) -> MagicMock:
    """Create a mock SignalVector with the given action."""
    signal = MagicMock()
    signal.action = action
    signal.size_factor = size_factor
    signal.confidence = 0.75
    signal.sub_scores = {"ma_signal": 0.7, "rsi": 0.65, "momentum": 0.6, "onchain_score": 0.5}
    return signal


def _make_tech_view() -> MagicMock:
    tech = MagicMock()
    tech.stance = "BULLISH"
    tech.consensus = "2/3"
    tech.confidence = 0.72
    tech.reasoning = "Tech looks strong."
    return tech


def _make_onchain_view() -> MagicMock:
    onchain = MagicMock()
    onchain.valuation = "FAIR"
    onchain.network_health = "STRONG"
    onchain.confidence = 0.68
    onchain.reasoning = "Network activity healthy."
    return onchain


def _make_sentiment_view() -> MagicMock:
    senti = MagicMock()
    senti.score = 0.3
    senti.regime = "GREED"
    senti.veto = False
    senti.reasoning = "Fear&Greed index 65 (Greed)."
    return senti


def _make_macro_regime() -> MagicMock:
    macro = MagicMock()
    macro.regime = "RISK_ON"
    macro.confidence = 0.8
    macro.drivers = ["Low real rates", "DXY weakening"]
    macro.reasoning = "Macro is risk-on."
    return macro


# ---------------------------------------------------------------------------
# BullResearchAgent Tests
# ---------------------------------------------------------------------------


class TestBullResearchAgent:
    """Tests for BullResearchAgent.build_case() Tool-Use pattern."""

    def _make_agent(self, llm_response: MagicMock) -> Any:
        """Build a BullResearchAgent with a mocked LLM client."""
        from backend.application.agents.bull_research_agent import BullResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = llm_response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered bull prompt"
        return BullResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

    @pytest.mark.asyncio
    async def test_build_case_returns_valid_bull_case(self) -> None:
        """BullResearchAgent.build_case() returns a validated BullCase from tool_use block."""
        from backend.domain.schemas.agent_schemas import BullCase

        tool_data = {
            "thesis": "BTC is about to moon because of strong on-chain metrics.",
            "strongest_points": ["MVRV-Z below 1", "Accumulation addresses growing"],
            "risks_acknowledged": ["Macro uncertainty", "Regulatory risk"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bull_case", tool_data))
        agent = self._make_agent(response)

        result = await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        assert isinstance(result, BullCase)
        assert result.thesis == tool_data["thesis"]
        assert result.strongest_points == tool_data["strongest_points"]
        assert result.risks_acknowledged == tool_data["risks_acknowledged"]

    @pytest.mark.asyncio
    async def test_build_case_passes_tool_choice_to_llm(self) -> None:
        """Assert that tool_choice is passed forcing the submit_bull_case tool."""
        tool_data = {
            "thesis": "Bullish thesis here.",
            "strongest_points": ["Point A", "Point B"],
            "risks_acknowledged": ["Risk A"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bull_case", tool_data))

        from backend.application.agents.bull_research_agent import BullResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BullResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        # Must include tool_choice forcing the named tool
        assert "tool_choice" in call_kwargs
        assert call_kwargs["tool_choice"]["type"] == "tool"
        assert call_kwargs["tool_choice"]["name"] == "submit_bull_case"

    @pytest.mark.asyncio
    async def test_build_case_passes_tools_with_bull_case_schema(self) -> None:
        """Assert that tools list contains BullCase.model_json_schema() as input_schema."""
        from backend.domain.schemas.agent_schemas import BullCase

        tool_data = {
            "thesis": "Strong bull case.",
            "strongest_points": ["A"],
            "risks_acknowledged": ["B"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bull_case", tool_data))

        from backend.application.agents.bull_research_agent import BullResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BullResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert "tools" in call_kwargs
        tools = call_kwargs["tools"]
        assert len(tools) >= 1
        tool_def = next(t for t in tools if t["name"] == "submit_bull_case")
        assert tool_def["input_schema"] == BullCase.model_json_schema()

    @pytest.mark.asyncio
    async def test_build_case_uses_sonnet_model(self) -> None:
        """BullResearchAgent must use claude-sonnet-4-6 (not Haiku)."""
        tool_data = {
            "thesis": "Thesis.",
            "strongest_points": ["P"],
            "risks_acknowledged": ["R"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bull_case", tool_data))

        from backend.application.agents.bull_research_agent import BullResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BullResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_build_case_no_tool_use_block_returns_fallback(self) -> None:
        """When LLM returns no tool_use block, agent handles gracefully (no uncaught exception)."""
        from backend.domain.schemas.agent_schemas import BullCase

        # Response with only a text block, no tool_use
        response = _make_llm_response(_make_text_block("I cannot provide the bull case right now."))

        from backend.application.agents.bull_research_agent import BullResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BullResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        # Should NOT raise, should return a BullCase (fallback)
        result = await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )
        assert isinstance(result, BullCase)


# ---------------------------------------------------------------------------
# BearResearchAgent Tests
# ---------------------------------------------------------------------------


class TestBearResearchAgent:
    """Tests for BearResearchAgent.build_case() Tool-Use pattern."""

    def _make_agent(self, llm_response: MagicMock) -> Any:
        """Build a BearResearchAgent with a mocked LLM client."""
        from backend.application.agents.bear_research_agent import BearResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = llm_response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered bear prompt"
        return BearResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

    @pytest.mark.asyncio
    async def test_build_case_returns_valid_bear_case(self) -> None:
        """BearResearchAgent.build_case() returns a validated BearCase from tool_use block."""
        from backend.domain.schemas.agent_schemas import BearCase

        tool_data = {
            "thesis": "BTC faces severe headwinds from regulatory pressure.",
            "strongest_points": [
                "SEC enforcement actions accelerating",
                "Mt. Gox repayments incoming",
            ],
            "counter_to_bull": ["MVRV-Z recovery is lagging", "On-chain volumes declining"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bear_case", tool_data))
        agent = self._make_agent(response)

        result = await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        assert isinstance(result, BearCase)
        assert result.thesis == tool_data["thesis"]
        assert result.strongest_points == tool_data["strongest_points"]
        assert result.counter_to_bull == tool_data["counter_to_bull"]

    @pytest.mark.asyncio
    async def test_build_case_passes_tool_choice_to_llm(self) -> None:
        """Assert that tool_choice is passed forcing the submit_bear_case tool."""
        tool_data = {
            "thesis": "Bearish thesis.",
            "strongest_points": ["Point A"],
            "counter_to_bull": ["Counter A"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bear_case", tool_data))

        from backend.application.agents.bear_research_agent import BearResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BearResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert "tool_choice" in call_kwargs
        assert call_kwargs["tool_choice"]["type"] == "tool"
        assert call_kwargs["tool_choice"]["name"] == "submit_bear_case"

    @pytest.mark.asyncio
    async def test_build_case_passes_tools_with_bear_case_schema(self) -> None:
        """Assert that tools list contains BearCase.model_json_schema() as input_schema."""
        from backend.domain.schemas.agent_schemas import BearCase

        tool_data = {
            "thesis": "Strong bear case.",
            "strongest_points": ["A"],
            "counter_to_bull": ["B"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bear_case", tool_data))

        from backend.application.agents.bear_research_agent import BearResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BearResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert "tools" in call_kwargs
        tools = call_kwargs["tools"]
        assert len(tools) >= 1
        tool_def = next(t for t in tools if t["name"] == "submit_bear_case")
        assert tool_def["input_schema"] == BearCase.model_json_schema()

    @pytest.mark.asyncio
    async def test_build_case_uses_sonnet_model(self) -> None:
        """BearResearchAgent must use claude-sonnet-4-6 (not Haiku)."""
        tool_data = {
            "thesis": "Thesis.",
            "strongest_points": ["P"],
            "counter_to_bull": ["C"],
        }
        response = _make_llm_response(_make_tool_use_block("submit_bear_case", tool_data))

        from backend.application.agents.bear_research_agent import BearResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BearResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_build_case_no_tool_use_block_returns_fallback(self) -> None:
        """When LLM returns no tool_use block, agent handles gracefully (no uncaught exception)."""
        from backend.domain.schemas.agent_schemas import BearCase

        response = _make_llm_response(_make_text_block("Cannot provide bear case."))

        from backend.application.agents.bear_research_agent import BearResearchAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        agent = BearResearchAgent(llm_client=mock_llm, prompt_loader=mock_prompts)

        result = await agent.build_case(
            tech=_make_tech_view(),
            onchain=_make_onchain_view(),
            senti=_make_sentiment_view(),
            macro=_make_macro_regime(),
            engine_signal=_make_signal(),
        )
        assert isinstance(result, BearCase)


# ---------------------------------------------------------------------------
# RiskAgent Tests
# ---------------------------------------------------------------------------


class TestRiskAgent:
    """Tests for RiskAgent.assess() — D-06 tests 2 (State-from-Tool) and 7 (No-Shorting)."""

    def _make_agent(
        self,
        llm_response: MagicMock,
        store_exposure: float = 0.3,
    ) -> Any:
        """Build a RiskAgent with a mocked LLM client and exposure Store."""
        from backend.application.agents.risk_agent import RiskAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = llm_response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered risk prompt"

        # Portfolio exposure Store/repository
        mock_store = AsyncMock()
        mock_store.get_exposure = AsyncMock(return_value=store_exposure)

        return (
            RiskAgent(
                llm_client=mock_llm,
                prompt_loader=mock_prompts,
                exposure_store=mock_store,
            ),
            mock_llm,
            mock_store,
        )

    def _make_verdict_data(
        self,
        approve: bool = True,
        max_size: float = 1.0,
        breaches: list[str] | None = None,
        reasoning: str = "Risk looks acceptable.",
    ) -> dict[str, Any]:
        return {
            "approve": approve,
            "max_size": max_size,
            "breaches": breaches or [],
            "reasoning": reasoning,
        }

    @pytest.mark.asyncio
    async def test_assess_returns_valid_risk_verdict(self) -> None:
        """RiskAgent.assess() returns a validated RiskVerdict from tool_use block."""
        from backend.domain.schemas.agent_schemas import RiskVerdict

        verdict_data = self._make_verdict_data()
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response)

        result = await agent.assess(coin="BTC", engine_signal=_make_signal("BUY", 1.0))

        assert isinstance(result, RiskVerdict)
        assert result.approve is True
        assert result.max_size == 1.0
        assert result.breaches == []

    @pytest.mark.asyncio
    async def test_assess_reads_exposure_from_store_not_llm(self) -> None:
        """D-06 test 2: RiskAgent reads exposure from Store; value appears in prompt context."""
        store_exposure = 0.42  # A specific known value from the store

        verdict_data = self._make_verdict_data(approve=True, max_size=0.8)
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))

        from backend.application.agents.risk_agent import RiskAgent

        mock_llm = AsyncMock()
        mock_llm.messages_create.return_value = response
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered risk prompt"
        mock_store = AsyncMock()
        mock_store.get_exposure = AsyncMock(return_value=store_exposure)

        agent = RiskAgent(
            llm_client=mock_llm,
            prompt_loader=mock_prompts,
            exposure_store=mock_store,
        )

        await agent.assess(coin="BTC", engine_signal=_make_signal("BUY", 1.0))

        # Store was called with the correct coin
        mock_store.get_exposure.assert_called_once_with("BTC")

        # The real exposure value must appear in the prompt rendered to the LLM
        # (not an LLM-hallucinated value). Check via prompt_loader.render call.
        render_calls = mock_prompts.render.call_args_list
        assert len(render_calls) >= 1
        # Find the call that includes exposure in context
        found_exposure_in_context = False
        for call in render_calls:
            ctx = call.args[1] if len(call.args) > 1 else call.kwargs.get("context", {})
            if isinstance(ctx, dict):
                # Check at top level and nested
                if ctx.get("current_exposure") == store_exposure:
                    found_exposure_in_context = True
                    break
                # Also accept if it's in any nested dict
                for v in ctx.values():
                    if v == store_exposure:
                        found_exposure_in_context = True
                        break
        assert found_exposure_in_context, (
            f"Store exposure {store_exposure} not found in any prompt render context. "
            f"Render calls: {render_calls}"
        )

    @pytest.mark.asyncio
    async def test_assess_sell_signal_forces_max_size_zero(self) -> None:
        """D-06 test 7: When engine_signal.action == 'SELL', returned max_size == 0.0."""
        # LLM returns max_size=1.0 but engine says SELL — Python must override to 0.0
        verdict_data = self._make_verdict_data(approve=False, max_size=1.0)
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response, store_exposure=0.5)

        result = await agent.assess(coin="BTC", engine_signal=_make_signal("SELL", 0.0))

        assert result.max_size == 0.0, (
            f"Expected max_size == 0.0 on SELL signal, got {result.max_size}"
        )

    @pytest.mark.asyncio
    async def test_assess_buy_signal_max_size_not_negative(self) -> None:
        """D-06 test 7: max_size is never negative for BUY or HOLD signal."""
        verdict_data = self._make_verdict_data(approve=True, max_size=0.8)
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response, store_exposure=0.1)

        result = await agent.assess(coin="BTC", engine_signal=_make_signal("BUY", 1.0))

        assert result.max_size >= 0.0, f"max_size must never be negative, got {result.max_size}"

    @pytest.mark.asyncio
    async def test_assess_hold_signal_max_size_not_negative(self) -> None:
        """D-06 test 7: max_size is never negative for HOLD signal."""
        verdict_data = self._make_verdict_data(approve=True, max_size=0.5)
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response, store_exposure=0.2)

        result = await agent.assess(coin="ETH", engine_signal=_make_signal("HOLD", 0.5))

        assert result.max_size >= 0.0

    @pytest.mark.asyncio
    async def test_assess_approves_false_when_breach_present(self) -> None:
        """RiskVerdict.approve == False when breaches are present."""
        from backend.domain.schemas.agent_schemas import RiskVerdict

        verdict_data = self._make_verdict_data(
            approve=False,
            max_size=0.0,
            breaches=["Max position limit exceeded", "Concentration risk: >30% in single asset"],
            reasoning="Position exceeds maximum allowed.",
        )
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response)

        result = await agent.assess(coin="BTC", engine_signal=_make_signal("BUY"))

        assert isinstance(result, RiskVerdict)
        assert result.approve is False
        assert len(result.breaches) > 0

    @pytest.mark.asyncio
    async def test_assess_llm_exception_returns_conservative_verdict(self) -> None:
        """On LLM Exception, RiskAgent returns conservative RiskVerdict (no raise)."""
        from backend.application.agents.risk_agent import RiskAgent
        from backend.domain.schemas.agent_schemas import RiskVerdict

        mock_llm = AsyncMock()
        mock_llm.messages_create.side_effect = RuntimeError("LLM service unavailable")
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "rendered prompt"
        mock_store = AsyncMock()
        mock_store.get_exposure = AsyncMock(return_value=0.3)

        agent = RiskAgent(
            llm_client=mock_llm,
            prompt_loader=mock_prompts,
            exposure_store=mock_store,
        )

        # Should NOT raise
        result = await agent.assess(coin="BTC", engine_signal=_make_signal("BUY"))

        assert isinstance(result, RiskVerdict)
        # Conservative: approve=False or max_size capped low
        assert result.approve is False or result.max_size <= 0.5

    @pytest.mark.asyncio
    async def test_assess_uses_sonnet_model(self) -> None:
        """RiskAgent must use claude-sonnet-4-6 (not Haiku)."""
        verdict_data = self._make_verdict_data()
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, mock_llm, _ = self._make_agent(response)

        await agent.assess(coin="BTC", engine_signal=_make_signal("BUY"))

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_assess_passes_tool_choice_to_llm(self) -> None:
        """RiskAgent passes tool_choice forcing the submit_risk_verdict tool."""
        verdict_data = self._make_verdict_data()
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, mock_llm, _ = self._make_agent(response)

        await agent.assess(coin="BTC", engine_signal=_make_signal("BUY"))

        call_kwargs = mock_llm.messages_create.call_args.kwargs
        assert "tool_choice" in call_kwargs
        assert call_kwargs["tool_choice"]["type"] == "tool"
        assert call_kwargs["tool_choice"]["name"] == "submit_risk_verdict"

    @pytest.mark.asyncio
    async def test_assess_sell_max_size_clamped_even_if_llm_returns_positive(self) -> None:
        """D-06 test 7: SELL → max_size always 0.0 regardless of what LLM says."""
        # LLM says max_size=0.9 (bullish verdict) but engine says SELL
        verdict_data = self._make_verdict_data(approve=True, max_size=0.9)
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response, store_exposure=0.1)

        result = await agent.assess(coin="BTC", engine_signal=_make_signal("SELL", 0.0))

        # Python post-LLM enforcement: SELL always forces max_size = 0.0
        assert result.max_size == 0.0

    @pytest.mark.asyncio
    async def test_assess_max_size_clamped_to_zero_minimum(self) -> None:
        """max_size is clamped to [0.0, 1.5] — negative values impossible."""
        # Verify via BUY path (cannot have negative via schema validation)
        verdict_data = self._make_verdict_data(approve=True, max_size=0.0)
        response = _make_llm_response(_make_tool_use_block("submit_risk_verdict", verdict_data))
        agent, _, _ = self._make_agent(response)

        result = await agent.assess(coin="ETH", engine_signal=_make_signal("BUY"))

        assert result.max_size >= 0.0
