from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.agents.cointelligence_agent import CointelligenceAgent
from backend.domain.schemas.multiagent_schemas import CointelligenceReport

pytestmark = pytest.mark.unit


def _make_agent(final_json: str | None = None) -> CointelligenceAgent:
    cg = AsyncMock()
    cg.get_market_data.return_value = [
        {
            "id": "bitcoin",
            "current_price": 95000.0,
            "market_cap": 1.8e12,
            "total_volume": 30e9,
            "price_change_percentage_24h_in_currency": 2.1,
        }
    ]
    fg = AsyncMock()
    fg.get.return_value = {"value": 55, "label": "Greed"}
    macro = AsyncMock()
    macro_ctx = MagicMock()
    macro_ctx.chf_eur = 0.935
    macro.get_context.return_value = macro_ctx
    llm = AsyncMock()

    tool_resp = MagicMock()
    tool_resp.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "get_coin_data"
    tool_block.id = "tu_1"
    tool_block.input = {"coin": "bitcoin"}
    tool_resp.content = [tool_block]

    final_resp = MagicMock()
    final_resp.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = (
        final_json
        or """{
        "price_chf": 88825.0,
        "mvrv_zone": "FAIR",
        "fear_greed": 55,
        "sharpe_crypto": 0.9,
        "sharpe_smi": 0.5,
        "chf_usd_impact": "NEUTRAL",
        "regime_signal": "HOLD",
        "max_allocation_pct": 5.0,
        "reasoning": "BTC ist fair bewertet laut MVRV.",
        "disclaimer": "Hochspekulative Anlage. Keine Anlageberatung."
    }"""
    )
    final_resp.content = [text_block]

    llm.messages_create.side_effect = [tool_resp, final_resp]
    return CointelligenceAgent(
        coingecko=cg, fear_greed=fg, macro_service=macro, llm_client=llm, glassnode_api_key=""
    )


@pytest.mark.asyncio
async def test_analyze_btc_returns_report():
    agent = _make_agent()
    report = await agent.analyze("BTC")
    assert isinstance(report, CointelligenceReport)
    assert report.coin == "BTC"
    assert report.regime_signal in ("ACCUMULATE", "HOLD", "CAUTION", "AVOID")
    assert report.max_allocation_pct <= 10.0
    assert len(report.disclaimer) > 10


@pytest.mark.asyncio
async def test_analyze_eth_works():
    agent = _make_agent()
    report = await agent.analyze("ETH")
    assert isinstance(report, CointelligenceReport)


@pytest.mark.asyncio
async def test_analyze_fallback_on_llm_error():
    cg = AsyncMock()
    cg.get_market_data.return_value = []
    fg = AsyncMock()
    fg.get.return_value = {"value": 50, "label": "Neutral"}
    macro = AsyncMock()
    ctx = MagicMock()
    ctx.chf_eur = 0.93
    macro.get_context.return_value = ctx
    llm = AsyncMock()
    llm.messages_create.side_effect = RuntimeError("API down")
    agent = CointelligenceAgent(
        coingecko=cg, fear_greed=fg, macro_service=macro, llm_client=llm, glassnode_api_key=""
    )
    report = await agent.analyze("BTC")
    assert isinstance(report, CointelligenceReport)
    assert report.regime_signal in ("ACCUMULATE", "HOLD", "CAUTION", "AVOID")
