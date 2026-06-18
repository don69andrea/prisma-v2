from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.agents.macro_agent_v2 import MacroAgentV2
from backend.domain.schemas.multiagent_schemas import MacroToolReport

pytestmark = pytest.mark.unit


def _make_macro_context() -> Any:
    ctx = MagicMock()
    ctx.leitzins = 0.25
    ctx.chf_eur = 0.935
    ctx.inflation_ch = 0.8
    ctx.climate = "neutral"
    return ctx


def _make_agent(final_json: str | None = None) -> MacroAgentV2:
    macro_service = AsyncMock()
    macro_service.get_context.return_value = _make_macro_context()
    llm = AsyncMock()

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "get_snb_rate"
    tool_block.id = "tu_1"
    tool_block.input = {}
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_json or (
        '{"score": 62.5, "chf_impact": "NEGATIV", "reasoning": "Starker CHF belastet Exporteure."}'
    )
    final_response.content = [text_block]

    llm.messages_create.side_effect = [tool_response, final_response]
    return MacroAgentV2(macro_service=macro_service, llm_client=llm)


@pytest.mark.asyncio
async def test_get_macro_report_returns_macro_tool_report():
    agent = _make_agent()
    report = await agent.get_macro_report("NESN.SW", sector="food")
    assert isinstance(report, MacroToolReport)
    assert report.ticker == "NESN.SW"
    assert 0.0 <= report.score <= 100.0


@pytest.mark.asyncio
async def test_get_macro_report_fallback_on_llm_error():
    macro_service = AsyncMock()
    macro_service.get_context.return_value = _make_macro_context()
    llm = AsyncMock()
    llm.messages_create.side_effect = RuntimeError("LLM down")
    agent = MacroAgentV2(macro_service=macro_service, llm_client=llm)
    report = await agent.get_macro_report("NESN.SW")
    assert isinstance(report, MacroToolReport)
    assert report.ticker == "NESN.SW"
