"""Regression tests for SignalDirector wiring bugs found during real API runs.

These tests caught bugs that were invisible to the existing fully-mocked test suite,
because MagicMock auto-creates any attribute — wrong method names and wrong arg counts
never raise during mocked tests.

Strategy: wire REAL agents with REAL SignalDirector and REAL signal_service;
mock ONLY LLMClient.messages_create (makes all LLM agents fall back to deterministic
values, which is fine — the pipeline must still complete without TypeError).

Bugs caught:
- OnChainAnalystAgent.analyze(coin, {}) → TypeError (takes 1 positional arg, got 2)
- MacroRegimeAgent called via .analyze() instead of .get_regime() → AttributeError
- signal_service.evaluate awaited via asyncio.to_thread despite being async def
- Coin "BTC-USD" not in prices_df columns; prices_df had column "BTC" → ValueError
- model_dump() embeds UUID object into JSON column → not JSON-serializable
- audit_repo.insert called with "BTC-USD" instead of base_coin "BTC"
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_prices_df(coin: str = "BTC") -> pd.DataFrame:
    """200-bar daily prices DataFrame with one column — mirrors dependencies.py stub."""
    rng = np.random.default_rng(seed=42)
    returns = rng.normal(0.001, 0.03, size=200)
    prices = 100.0 * np.cumprod(1 + returns)
    idx = pd.date_range(
        end=datetime.now(UTC), periods=200, freq="D", tz="UTC"
    )
    return pd.DataFrame({coin: prices}, index=idx)


def _make_llm_raises() -> AsyncMock:
    """LLMClient that always raises — agents fall back to deterministic values."""
    llm = AsyncMock()
    llm.messages_create.side_effect = Exception("LLM mocked away")
    return llm


def _make_prompts() -> MagicMock:
    prompts = MagicMock()
    prompts.render.return_value = "mocked prompt"
    return prompts


def _build_director(prices_df: pd.DataFrame) -> tuple[Any, MagicMock]:
    """Wire real SignalDirector + real agents; mock only LLM + audit_repo."""
    from backend.application.agents.bear_research_agent import BearResearchAgent
    from backend.application.agents.bull_research_agent import BullResearchAgent
    from backend.application.agents.macro_regime_agent import MacroRegimeAgent
    from backend.application.agents.onchain_analyst_agent import OnChainAnalystAgent
    from backend.application.agents.risk_agent import RiskAgent
    from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent
    from backend.application.agents.signal_director import SignalDirector
    from backend.application.agents.technical_analyst_agent import TechnicalAnalystAgent
    from backend.application.signals import signal_service

    llm = _make_llm_raises()
    prompts = _make_prompts()

    class _StubExposureStore:
        async def get_exposure(self, coin: str) -> float:  # noqa: ARG002
            return 0.0

    # SentimentAgent needs a DB session; make it raise so it falls back gracefully
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("no DB in unit test")

    mock_news_retrieval = AsyncMock()

    audit_repo = MagicMock()
    audit_repo.insert = AsyncMock(return_value=uuid.uuid4())

    director = SignalDirector(
        signal_service=signal_service,
        tech_agent=TechnicalAnalystAgent(llm_client=llm, prompt_loader=prompts),
        onchain_agent=OnChainAnalystAgent(llm_client=llm, prompt_loader=prompts),
        senti_agent=SentimentAnalystAgent(
            db_session=mock_session,
            news_retrieval_service=mock_news_retrieval,
            llm_client=llm,
            prompt_loader=prompts,
        ),
        macro_agent=MacroRegimeAgent(llm_client=llm, prompt_loader=prompts),
        bull_agent=BullResearchAgent(llm_client=llm, prompt_loader=prompts),
        bear_agent=BearResearchAgent(llm_client=llm, prompt_loader=prompts),
        risk_agent=RiskAgent(
            llm_client=llm,
            prompt_loader=prompts,
            exposure_store=_StubExposureStore(),
        ),
        audit_repo=audit_repo,
        prices_df=prices_df,
    )
    return director, audit_repo


# ---------------------------------------------------------------------------
# Wiring tests — use real agents, only LLM mocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_btcusd_produces_trade_signal():
    """director.run("BTC-USD") must complete without TypeError/AttributeError.

    Before fixes this raised:
      TypeError: OnChainAnalystAgent.analyze() takes 2 positional arguments but 3 were given
    Then:
      AttributeError: MacroRegimeAgent has no .analyze() method
    Then:
      TypeError: signal_service.evaluate object can't be used in 'await' expression
    """
    from backend.domain.schemas.agent_schemas import TradeSignal

    prices_df = _make_stub_prices_df("BTC")
    director, _ = _build_director(prices_df)

    result = await director.run("BTC-USD")

    assert isinstance(result, TradeSignal)
    assert result.action in ("BUY", "HOLD", "SELL")
    assert result.audit_trail_id is not None


@pytest.mark.asyncio
async def test_prices_df_column_renamed_for_non_btc_coin():
    """run("ETH-USD") must succeed even when prices_df only has column "BTC".

    Before fix this raised:
      ValueError: Coin 'ETH' not in prices_df (available: ['BTC'])
    The fix strips the suffix and renames the stub column.
    """
    from backend.domain.schemas.agent_schemas import TradeSignal

    # prices_df intentionally has "BTC" as the column, not "ETH"
    prices_df = _make_stub_prices_df("BTC")
    director, _ = _build_director(prices_df)

    result = await director.run("ETH-USD")

    assert isinstance(result, TradeSignal)


@pytest.mark.asyncio
async def test_coin_suffix_stripped_in_audit_insert():
    """audit_repo.insert must be called with base_coin "BTC", not "BTC-USD".

    Before fix, the audit trail stored "BTC-USD", causing 404 on
    GET /api/v1/crypto/BTC/agent-audit which searches for "BTC".
    """
    prices_df = _make_stub_prices_df("BTC")
    director, audit_repo = _build_director(prices_df)

    await director.run("BTC-USD")

    audit_repo.insert.assert_called_once()
    coin_arg = audit_repo.insert.call_args[0][0]
    assert coin_arg == "BTC", (
        f"Expected insert called with 'BTC', got '{coin_arg}'. "
        "The suffix must be stripped before persisting."
    )


@pytest.mark.asyncio
async def test_agent_run_dict_is_json_serializable():
    """The agent_run dict passed to audit_repo.insert must be json.dumps-able.

    Before fix, model_dump() produced UUID objects → json.dumps() raised
    TypeError: Object of type UUID is not JSON serializable.
    Fix: model_dump(mode="json") converts UUIDs to strings.
    """
    prices_df = _make_stub_prices_df("BTC")
    director, audit_repo = _build_director(prices_df)

    await director.run("BTC-USD")

    audit_repo.insert.assert_called_once()
    agent_run_dict = audit_repo.insert.call_args[0][2]

    # Must not raise — if it does, UUIDs or other non-serializable types leaked in
    serialized = json.dumps(agent_run_dict)
    assert len(serialized) > 0
    assert "[DEMO-DATEN]" not in serialized
