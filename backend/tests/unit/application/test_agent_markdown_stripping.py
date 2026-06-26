"""Regression tests for LLM markdown fence stripping in text-based agents.

Haiku wraps its JSON responses in ```json ... ``` fences, causing json.loads() to
fail with "Expecting value: line 1 column 1 (char 0)". Three agents were affected:
  - TechnicalAnalystAgent
  - OnChainAnalystAgent
  - MacroRegimeAgent

Fix: strip leading ``` lines before calling json.loads().

These tests verify:
  1. Plain JSON (no fences) parses correctly.
  2. JSON wrapped in ```json...``` fences parses correctly.
  3. JSON wrapped in plain ```...``` (no language tag) parses correctly.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> Any:
    """Fake Anthropic SDK response object with a single text content block."""
    block = SimpleNamespace(text=text)
    return SimpleNamespace(content=[block])


def _make_prompts() -> MagicMock:
    m = MagicMock()
    m.render.return_value = "mocked prompt"
    return m


VALID_TECHNICAL_JSON = json.dumps(
    {
        "coin": "BTC",
        "stance": "BULLISH",
        "consensus": "4/5",
        "key_signals": ["RSI=0.70"],
        "confidence": 0.80,
        "reasoning": "Strong momentum.",
    }
)

VALID_ONCHAIN_JSON = json.dumps(
    {
        "coin": "BTC",
        "valuation": "FAIR",
        "network_health": "STRONG",
        "confidence": 0.75,
        "reasoning": "NVT in normal range.",
    }
)

VALID_MACRO_JSON = json.dumps(
    {
        "regime": "RISK_ON",
        "drivers": ["low real rates"],
        "confidence": 0.80,
        "reasoning": "DXY weakening.",
    }
)


# ---------------------------------------------------------------------------
# TechnicalAnalystAgent
# ---------------------------------------------------------------------------


class TestTechnicalAnalystAgentMarkdownStripping:
    def _make_agent(self, response_text: str) -> Any:
        from backend.application.agents.technical_analyst_agent import TechnicalAnalystAgent

        llm = AsyncMock()
        llm.messages_create.return_value = _make_text_response(response_text)
        return TechnicalAnalystAgent(llm_client=llm, prompt_loader=_make_prompts())

    @pytest.mark.asyncio
    async def test_plain_json_parses(self):
        agent = self._make_agent(VALID_TECHNICAL_JSON)
        result = await agent.analyze("BTC", {})
        assert result.stance == "BULLISH"
        assert result.confidence == 0.80

    @pytest.mark.asyncio
    async def test_json_with_json_fence_parses(self):
        fenced = f"```json\n{VALID_TECHNICAL_JSON}\n```"
        agent = self._make_agent(fenced)
        result = await agent.analyze("BTC", {})
        assert result.stance == "BULLISH"
        assert result.confidence == 0.80

    @pytest.mark.asyncio
    async def test_json_with_plain_fence_parses(self):
        fenced = f"```\n{VALID_TECHNICAL_JSON}\n```"
        agent = self._make_agent(fenced)
        result = await agent.analyze("BTC", {})
        assert result.stance == "BULLISH"

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back(self):
        from backend.domain.schemas.agent_schemas import TechnicalView

        agent = self._make_agent("this is not json")
        result = await agent.analyze("BTC", {"rsi": 0.3})
        # Falls back to deterministic BEARISH (rsi=0.3 < 0.4)
        assert isinstance(result, TechnicalView)
        assert result.confidence == 0.4


# ---------------------------------------------------------------------------
# OnChainAnalystAgent
# ---------------------------------------------------------------------------


class TestOnChainAnalystAgentMarkdownStripping:
    def _make_agent(self, response_text: str) -> Any:
        from backend.application.agents.onchain_analyst_agent import OnChainAnalystAgent

        llm = AsyncMock()
        llm.messages_create.return_value = _make_text_response(response_text)
        return OnChainAnalystAgent(llm_client=llm, prompt_loader=_make_prompts())

    @pytest.mark.asyncio
    async def test_plain_json_parses(self):
        agent = self._make_agent(VALID_ONCHAIN_JSON)
        result = await agent.analyze("BTC")
        assert result.valuation == "FAIR"
        assert result.network_health == "STRONG"

    @pytest.mark.asyncio
    async def test_json_fence_stripped(self):
        fenced = f"```json\n{VALID_ONCHAIN_JSON}\n```"
        agent = self._make_agent(fenced)
        result = await agent.analyze("BTC")
        assert result.valuation == "FAIR"

    @pytest.mark.asyncio
    async def test_analyze_takes_exactly_one_arg(self):
        """OnChainAnalystAgent.analyze(coin) — must NOT accept a second positional arg.

        Before fix, SignalDirector called analyze(coin, {}) → TypeError.
        """
        import inspect

        from backend.application.agents.onchain_analyst_agent import OnChainAnalystAgent

        sig = inspect.signature(OnChainAnalystAgent.analyze)
        params = list(sig.parameters)
        # params[0] is 'self', params[1] is 'coin' — no third param allowed
        assert len(params) == 2, (
            f"OnChainAnalystAgent.analyze must take exactly 1 arg (coin), got params={params}. "
            "Callers must NOT pass a second arg."
        )


# ---------------------------------------------------------------------------
# MacroRegimeAgent
# ---------------------------------------------------------------------------


class TestMacroRegimeAgentMarkdownStripping:
    def _make_agent(self, response_text: str) -> Any:
        from backend.application.agents.macro_regime_agent import MacroRegimeAgent

        llm = AsyncMock()
        llm.messages_create.return_value = _make_text_response(response_text)
        return MacroRegimeAgent(llm_client=llm, prompt_loader=_make_prompts())

    @pytest.mark.asyncio
    async def test_plain_json_parses(self):
        agent = self._make_agent(VALID_MACRO_JSON)
        result = await agent._fetch_regime()
        assert result.regime == "RISK_ON"
        assert result.confidence == 0.80

    @pytest.mark.asyncio
    async def test_json_fence_stripped(self):
        fenced = f"```json\n{VALID_MACRO_JSON}\n```"
        agent = self._make_agent(fenced)
        result = await agent._fetch_regime()
        assert result.regime == "RISK_ON"

    @pytest.mark.asyncio
    async def test_method_is_get_regime_not_analyze(self):
        """MacroRegimeAgent must expose get_regime(), not analyze().

        Before fix, SignalDirector called .analyze() which doesn't exist → AttributeError.
        """
        from backend.application.agents.macro_regime_agent import MacroRegimeAgent

        assert hasattr(MacroRegimeAgent, "get_regime"), (
            "MacroRegimeAgent must have get_regime() method. "
            "SignalDirector calls .get_regime(), not .analyze()."
        )
        assert not hasattr(MacroRegimeAgent, "analyze"), (
            "MacroRegimeAgent must NOT have .analyze() — "
            "SignalDirector was fixed to call .get_regime(); adding .analyze() back would be a regression."
        )
