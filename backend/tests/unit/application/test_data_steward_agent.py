from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from backend.application.agents.data_steward_agent import DataStewardAgent, DataStewardReport

pytestmark = pytest.mark.unit


def _make_agent(price_age_hours: int = 48, last_price: float = 100.0):
    repo = AsyncMock()
    mock_stock = MagicMock()
    mock_stock.ticker = "NESN.SW"
    mock_stock.last_updated_at = datetime.now(UTC) - timedelta(hours=price_age_hours)
    mock_stock.last_price = last_price
    repo.list_all.return_value = [mock_stock]

    yf = AsyncMock()
    yf.get_latest_price.return_value = 105.2

    macro = AsyncMock()
    macro_ctx = MagicMock()
    macro_ctx.fetched_at = datetime.now(UTC) - timedelta(hours=8)
    macro.get_context.return_value = macro_ctx

    return DataStewardAgent(stock_repo=repo, yf_adapter=yf, macro_service=macro)


@pytest.mark.asyncio
async def test_stale_price_triggers_refresh():
    agent = _make_agent(price_age_hours=40)  # > 36h threshold
    report = await agent.run_check()
    assert isinstance(report, DataStewardReport)
    assert "NESN.SW" in report.refreshed_tickers


@pytest.mark.asyncio
async def test_fresh_price_no_refresh():
    agent = _make_agent(price_age_hours=10)  # < 36h
    report = await agent.run_check()
    assert "NESN.SW" not in report.refreshed_tickers


@pytest.mark.asyncio
async def test_price_spike_quarantined():
    repo = AsyncMock()
    mock_stock = MagicMock()
    mock_stock.ticker = "NESN.SW"
    mock_stock.last_updated_at = datetime.now(UTC) - timedelta(hours=40)
    mock_stock.last_price = 100.0
    repo.list_all.return_value = [mock_stock]
    yf = AsyncMock()
    yf.get_latest_price.return_value = 120.0  # +20% → Spike
    macro = AsyncMock()
    macro.get_context.return_value = MagicMock()
    agent = DataStewardAgent(stock_repo=repo, yf_adapter=yf, macro_service=macro)
    report = await agent.run_check()
    assert "NESN.SW" in report.quarantined_tickers
