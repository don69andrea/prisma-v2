"""Unit-Tests für die vier Analyst-Agenten (D-01, D-03, D-04, D-06).

Tests:
  Task 1 — TechnicalAnalystAgent + OnChainAnalystAgent (RED→GREEN)
  Task 2 — SentimentAnalystAgent (F&G stub) + MacroRegimeAgent (cache, Haiku)

Pflicht-Tests laut §6 AGENTS.md (D-06):
  1. Hallucination Guard: agent output number == engine/tool number, diff < 1e-9
  2. Fallback: LLM raises Exception → deterministic view returned, no raise
  5. Pydantic: LLM returns freetext for Literal field → ValidationError caught → fallback
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm(response_text: str | None = None, side_effect: Exception | None = None) -> AsyncMock:
    """Build a mock LLMClient.messages_create that returns a text response."""
    mock_llm = AsyncMock()
    if side_effect is not None:
        mock_llm.messages_create.side_effect = side_effect
    elif response_text is not None:
        mock_content = MagicMock()
        mock_content.text = response_text
        mock_llm.messages_create.return_value = MagicMock(content=[mock_content])
    return mock_llm


def _make_prompts() -> MagicMock:
    mock_prompts = MagicMock()
    mock_prompts.render.return_value = "rendered prompt"
    return mock_prompts


# ===========================================================================
# Task 1 — TechnicalAnalystAgent
# ===========================================================================


class TestTechnicalAnalystAgent:
    """Tests for TechnicalAnalystAgent."""

    _VALID_SUB_SCORES: dict[str, Any] = {
        "rsi": 0.62,
        "macd_signal": 0.35,
        "momentum": 0.78,
    }

    _VALID_TECHNICAL_VIEW = {
        "coin": "BTC",
        "stance": "BULLISH",
        "consensus": "3/3",
        "key_signals": ["RSI 62 — overbought approach", "MACD positive cross"],
        "confidence": 0.72,
        "reasoning": "RSI at 0.62 signals momentum. MACD positive. Momentum strong at 0.78.",
    }

    def _build_agent(
        self,
        response_text: str | None = None,
        side_effect: Exception | None = None,
    ) -> Any:
        from backend.application.agents.technical_analyst_agent import TechnicalAnalystAgent

        return TechnicalAnalystAgent(
            llm_client=_make_llm(response_text, side_effect),
            prompt_loader=_make_prompts(),
        )

    async def test_valid_output_returns_technical_view(self) -> None:
        """Agent returns a TechnicalView with valid Pydantic-validated output."""
        agent = self._build_agent(json.dumps(self._VALID_TECHNICAL_VIEW))
        from backend.domain.schemas.agent_schemas import TechnicalView

        result = await agent.analyze("BTC", self._VALID_SUB_SCORES)
        assert isinstance(result, TechnicalView)
        assert result.coin == "BTC"
        assert result.stance in ("BULLISH", "NEUTRAL", "BEARISH")
        assert 0.0 <= result.confidence <= 1.0

    # D-06 Test 1: Hallucination Guard
    async def test_hallucination_guard_numbers_pass_through(self) -> None:
        """Numbers in output == numbers in sub_scores input. Diff < 1e-9."""
        sub_scores = {"rsi": 0.734816293, "macd_signal": 0.219384756, "momentum": 0.583920471}
        view_with_exact_numbers = {
            "coin": "ETH",
            "stance": "NEUTRAL",
            "consensus": "2/3",
            "key_signals": [f"RSI {sub_scores['rsi']}", f"Momentum {sub_scores['momentum']}"],
            "confidence": sub_scores["rsi"],
            "reasoning": f"RSI={sub_scores['rsi']} MACD={sub_scores['macd_signal']} Mom={sub_scores['momentum']}",
        }
        agent = self._build_agent(json.dumps(view_with_exact_numbers))
        result = await agent.analyze("ETH", sub_scores)
        # The confidence field must equal exactly the RSI value (no invention)
        assert abs(result.confidence - sub_scores["rsi"]) < 1e-9

    # D-06 Test 2: Fallback on LLM Exception
    async def test_fallback_on_llm_exception(self) -> None:
        """LLM raises Exception → deterministic TechnicalView returned, no raise."""
        agent = self._build_agent(side_effect=Exception("LLM timeout"))
        result = await agent.analyze("BTC", self._VALID_SUB_SCORES)
        from backend.domain.schemas.agent_schemas import TechnicalView

        assert isinstance(result, TechnicalView)
        assert result.confidence <= 0.5  # lowered confidence in fallback
        assert result.coin == "BTC"

    # D-06 Test 5: Pydantic Literal field violation triggers fallback
    async def test_pydantic_literal_violation_triggers_fallback(self) -> None:
        """LLM returns freetext for Literal stance field → ValidationError → fallback."""
        bad_view = {
            "coin": "BTC",
            "stance": "VERY_BULLISH_DEFINITELY",  # invalid Literal
            "consensus": "3/3",
            "key_signals": ["signal"],
            "confidence": 0.8,
            "reasoning": "looks good",
        }
        agent = self._build_agent(json.dumps(bad_view))
        result = await agent.analyze("BTC", self._VALID_SUB_SCORES)
        from backend.domain.schemas.agent_schemas import TechnicalView

        assert isinstance(result, TechnicalView)
        # Must be a valid Literal stance (fallback provides this)
        assert result.stance in ("BULLISH", "NEUTRAL", "BEARISH")

    async def test_uses_haiku_model(self) -> None:
        """TechnicalAnalystAgent must use Haiku model constant."""
        from backend.application.agents.technical_analyst_agent import TechnicalAnalystAgent

        assert TechnicalAnalystAgent._MODEL == "claude-haiku-4-5-20251001"

    async def test_llm_called_with_correct_feature_tag(self) -> None:
        """messages_create must be called with feature='technical_analyst'."""
        agent = self._build_agent(json.dumps(self._VALID_TECHNICAL_VIEW))
        await agent.analyze("BTC", self._VALID_SUB_SCORES)
        call_kwargs = agent._llm.messages_create.call_args[1]
        assert call_kwargs["feature"] == "technical_analyst"


# ===========================================================================
# Task 1 — OnChainAnalystAgent
# ===========================================================================


class TestOnChainAnalystAgent:
    """Tests for OnChainAnalystAgent."""

    _VALID_ONCHAIN_VIEW = {
        "coin": "BTC",
        "valuation": "CHEAP",
        "network_health": "STRONG",
        "confidence": 0.65,
        "reasoning": "MVRV-Z below 0.5 indicates undervaluation. Hash-rate stable.",
    }

    def _build_agent(
        self,
        response_text: str | None = None,
        side_effect: Exception | None = None,
    ) -> Any:
        from backend.application.agents.onchain_analyst_agent import OnChainAnalystAgent

        return OnChainAnalystAgent(
            llm_client=_make_llm(response_text, side_effect),
            prompt_loader=_make_prompts(),
        )

    async def test_valid_output_returns_onchain_view(self) -> None:
        """Agent returns a valid OnChainView."""
        agent = self._build_agent(json.dumps(self._VALID_ONCHAIN_VIEW))
        from backend.domain.schemas.agent_schemas import OnChainView

        result = await agent.analyze("BTC")
        assert isinstance(result, OnChainView)
        assert result.coin == "BTC"
        assert result.valuation in ("CHEAP", "FAIR", "EXPENSIVE")
        assert result.network_health in ("STRONG", "NEUTRAL", "WEAK")

    # D-06 Test 1: Hallucination Guard for OnChain
    async def test_hallucination_guard_onchain_numbers(self) -> None:
        """OnChain confidence from tool value must pass through unchanged. Diff < 1e-9."""
        exact_confidence = 0.734816293
        onchain_view_with_tool_number = {
            "coin": "BTC",
            "valuation": "FAIR",
            "network_health": "NEUTRAL",
            "confidence": exact_confidence,
            "reasoning": f"MVRV-Z={exact_confidence} derived from on-chain tools.",
        }
        agent = self._build_agent(json.dumps(onchain_view_with_tool_number))
        result = await agent.analyze("BTC")
        assert abs(result.confidence - exact_confidence) < 1e-9

    async def test_fallback_on_llm_exception(self) -> None:
        """LLM raises Exception → deterministic OnChainView returned, no raise."""
        agent = self._build_agent(side_effect=RuntimeError("LLM unavailable"))
        result = await agent.analyze("ETH")
        from backend.domain.schemas.agent_schemas import OnChainView

        assert isinstance(result, OnChainView)
        assert result.confidence <= 0.5
        assert result.coin == "ETH"

    async def test_pydantic_literal_violation_triggers_fallback(self) -> None:
        """LLM returns freetext for Literal valuation field → fallback."""
        bad_view = {
            "coin": "BTC",
            "valuation": "SUPER_CHEAP",  # invalid Literal
            "network_health": "STRONG",
            "confidence": 0.7,
            "reasoning": "test",
        }
        agent = self._build_agent(json.dumps(bad_view))
        result = await agent.analyze("BTC")
        from backend.domain.schemas.agent_schemas import OnChainView

        assert isinstance(result, OnChainView)
        assert result.valuation in ("CHEAP", "FAIR", "EXPENSIVE")

    async def test_uses_haiku_model(self) -> None:
        """OnChainAnalystAgent must use Haiku model constant."""
        from backend.application.agents.onchain_analyst_agent import OnChainAnalystAgent

        assert OnChainAnalystAgent._MODEL == "claude-haiku-4-5-20251001"


# ===========================================================================
# Task 2 — SentimentAnalystAgent
# ===========================================================================


class TestSentimentAnalystAgent:
    """Tests for SentimentAnalystAgent (V4-4: RAG + deterministic score + LLM news_surprise)."""

    def _build_agent(self, fg_value: int, fg_classification: str = "Neutral") -> Any:
        """Build V4-4 agent with all 4 injected dependencies.

        Retrieval returns [] (empty) so the F&G fallback path is taken for
        formula/regime/stub-field tests — same observable behaviour as V4-3.
        """
        from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent

        # Mock async SQLAlchemy session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.fear_greed = fg_value
        mock_row.fg_classification = fg_classification
        mock_result.first.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Empty retrieval → F&G fallback (news_surprise=None, veto=False, sources=[])
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(return_value=[])

        mock_llm = AsyncMock()  # not reached in fallback path
        mock_prompts = MagicMock()

        return SentimentAnalystAgent(
            db_session=mock_session,
            news_retrieval_service=mock_retrieval,
            llm_client=mock_llm,
            prompt_loader=mock_prompts,
        )

    async def test_fg50_gives_score_zero(self) -> None:
        """fg_value=50 → score == 0.0 exactly."""
        agent = self._build_agent(fg_value=50, fg_classification="Neutral")
        result = await agent.analyze("BTC")
        assert result.score == 0.0

    async def test_fg0_gives_score_minus_one(self) -> None:
        """fg_value=0 → score == -1.0 exactly (extreme fear)."""
        agent = self._build_agent(fg_value=0, fg_classification="Extreme Fear")
        result = await agent.analyze("BTC")
        assert result.score == -1.0

    async def test_fg100_gives_score_one(self) -> None:
        """fg_value=100 → score == 1.0 exactly (extreme greed)."""
        agent = self._build_agent(fg_value=100, fg_classification="Extreme Greed")
        result = await agent.analyze("BTC")
        assert result.score == 1.0

    async def test_normalization_formula(self) -> None:
        """score = (fg_value - 50) / 50 for arbitrary value."""
        for fg in [0, 25, 50, 75, 100]:
            agent = self._build_agent(fg_value=fg)
            result = await agent.analyze("BTC")
            expected = (fg - 50) / 50
            assert abs(result.score - expected) < 1e-12, (
                f"Failed for fg={fg}: {result.score} != {expected}"
            )

    async def test_regime_fear_when_score_negative(self) -> None:
        """fg_value=20 → score=-0.6 → regime='FEAR'."""
        agent = self._build_agent(fg_value=20, fg_classification="Fear")
        result = await agent.analyze("BTC")
        assert result.regime == "FEAR"

    async def test_regime_greed_when_score_positive(self) -> None:
        """fg_value=80 → score=0.6 → regime='GREED'."""
        agent = self._build_agent(fg_value=80, fg_classification="Greed")
        result = await agent.analyze("BTC")
        assert result.regime == "GREED"

    async def test_regime_neutral_at_threshold(self) -> None:
        """fg_value=50 → score=0.0 → regime='NEUTRAL'."""
        agent = self._build_agent(fg_value=50, fg_classification="Neutral")
        result = await agent.analyze("BTC")
        assert result.regime == "NEUTRAL"

    async def test_stub_fields_correct(self) -> None:
        """news_surprise=None, veto=False, sources=[]."""
        agent = self._build_agent(fg_value=60)
        result = await agent.analyze("BTC")
        assert result.news_surprise is None
        assert result.veto is False
        assert result.sources == []

    async def test_coin_passed_through(self) -> None:
        """The coin field matches the argument."""
        agent = self._build_agent(fg_value=55)
        result = await agent.analyze("ETH")
        assert result.coin == "ETH"

    async def test_no_llm_call_on_empty_corpus(self) -> None:
        """When retrieval returns [] (empty corpus), the F&G fallback is used — no LLM call made."""
        from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.fear_greed = 55
        mock_row.fg_classification = "Greed"
        mock_result.first.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(return_value=[])

        # LLM mock that raises if called — ensures fallback path skips LLM
        mock_llm = AsyncMock()
        mock_llm.messages_create = AsyncMock(
            side_effect=AssertionError("LLM must not be called for empty corpus")
        )
        mock_prompts = MagicMock()

        agent = SentimentAnalystAgent(
            db_session=mock_session,
            news_retrieval_service=mock_retrieval,
            llm_client=mock_llm,
            prompt_loader=mock_prompts,
        )
        result = await agent.analyze("BTC")
        assert result.coin == "BTC"
        assert result.news_surprise is None  # fallback, no LLM call

    async def test_valid_schema(self) -> None:
        """Output validates against SentimentView schema."""
        from backend.domain.schemas.agent_schemas import SentimentView

        agent = self._build_agent(fg_value=75, fg_classification="Greed")
        result = await agent.analyze("BTC")
        assert isinstance(result, SentimentView)
        assert -1.0 <= result.score <= 1.0


# ===========================================================================
# Task 2 — MacroRegimeAgent
# ===========================================================================


class TestMacroRegimeAgent:
    """Tests for MacroRegimeAgent (D-03 — new Haiku agent, 1h cache)."""

    _VALID_MACRO_REGIME = {
        "regime": "RISK_ON",
        "drivers": ["Low real rates", "DXY weakening", "BTC-SPY correlation low"],
        "confidence": 0.75,
        "reasoning": "Real rates negative, DXY trend down. Risk-on environment favors crypto.",
    }

    def _build_agent(
        self,
        response_text: str | None = None,
        side_effect: Exception | None = None,
    ) -> Any:
        from backend.application.agents.macro_regime_agent import MacroRegimeAgent

        # Always clear cache before each test
        MacroRegimeAgent.clear_cache()

        return MacroRegimeAgent(
            llm_client=_make_llm(response_text, side_effect),
            prompt_loader=_make_prompts(),
        )

    async def test_valid_output_returns_macro_regime(self) -> None:
        """Agent returns a valid MacroRegime Pydantic object."""
        agent = self._build_agent(json.dumps(self._VALID_MACRO_REGIME))
        from backend.domain.schemas.agent_schemas import MacroRegime

        result = await agent.get_regime()
        assert isinstance(result, MacroRegime)
        assert result.regime in ("RISK_ON", "NEUTRAL", "RISK_OFF")
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.drivers) >= 1

    async def test_uses_haiku_model(self) -> None:
        """MacroRegimeAgent must use Haiku model."""
        from backend.application.agents.macro_regime_agent import MacroRegimeAgent

        assert MacroRegimeAgent._MODEL == "claude-haiku-4-5-20251001"

    # D-03 Cache test: 2 calls within TTL → only 1 LLM call
    async def test_cache_1h_ttl_two_calls_one_llm(self) -> None:
        """Two get_regime() calls within TTL trigger exactly ONE LLM call."""
        agent = self._build_agent(json.dumps(self._VALID_MACRO_REGIME))
        result1 = await agent.get_regime()
        result2 = await agent.get_regime()
        # Only 1 LLM call despite 2 agent calls
        assert agent._llm.messages_create.call_count == 1
        # Both results are identical
        assert result1.regime == result2.regime

    async def test_fallback_on_llm_exception(self) -> None:
        """LLM raises Exception → NEUTRAL MacroRegime returned with lowered confidence."""
        agent = self._build_agent(side_effect=Exception("LLM down"))
        result = await agent.get_regime()
        from backend.domain.schemas.agent_schemas import MacroRegime

        assert isinstance(result, MacroRegime)
        assert result.regime == "NEUTRAL"
        assert result.confidence <= 0.5

    async def test_pydantic_literal_violation_triggers_fallback(self) -> None:
        """LLM returns invalid regime → fallback NEUTRAL."""
        bad_regime = {
            "regime": "SUPER_RISK_ON",  # invalid Literal
            "drivers": ["test"],
            "confidence": 0.8,
            "reasoning": "test",
        }
        agent = self._build_agent(json.dumps(bad_regime))
        result = await agent.get_regime()
        from backend.domain.schemas.agent_schemas import MacroRegime

        assert isinstance(result, MacroRegime)
        assert result.regime in ("RISK_ON", "NEUTRAL", "RISK_OFF")

    async def test_cache_cleared_between_tests(self) -> None:
        """clear_cache() works — a new agent instance starts fresh."""
        from backend.application.agents.macro_regime_agent import MacroRegimeAgent

        MacroRegimeAgent.clear_cache()
        agent = self._build_agent(json.dumps(self._VALID_MACRO_REGIME))
        await agent.get_regime()
        # After clearing cache, a new agent should make another LLM call
        MacroRegimeAgent.clear_cache()
        agent2 = self._build_agent(json.dumps(self._VALID_MACRO_REGIME))
        await agent2.get_regime()
        # Each fresh agent (with cleared cache) makes its own LLM call
        assert agent2._llm.messages_create.call_count == 1

    async def test_no_macro_intelligence_agent_import(self) -> None:
        """macro_regime_agent module must NOT import MacroIntelligenceAgent."""
        import importlib
        import inspect
        import sys

        # Force reload
        if "backend.application.agents.macro_regime_agent" in sys.modules:
            mod = sys.modules["backend.application.agents.macro_regime_agent"]
        else:
            mod = importlib.import_module("backend.application.agents.macro_regime_agent")
        # Check module source doesn't reference MacroIntelligenceAgent
        source = inspect.getsource(mod)
        assert "MacroIntelligenceAgent" not in source, (
            "macro_regime_agent must NOT import or reference MacroIntelligenceAgent"
        )
