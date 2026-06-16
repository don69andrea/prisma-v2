"""Unit-Tests für ChatService."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.application.services.chat_service import (
    ChatMessage,
    ChatService,
    _dispatch_tool,
    _get_factsheet,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_dispatch_tool_search_stocks() -> None:
    nesn = MagicMock()
    nesn.ticker = "NESN"
    nesn.name = "Nestlé S.A."
    novn = MagicMock()
    novn.ticker = "NOVN"
    novn.name = "Novartis AG"

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_svc = AsyncMock()
    mock_svc.list_smi_stocks = AsyncMock(return_value=[nesn, novn])

    with (
        patch(
            "backend.infrastructure.persistence.session.get_session_factory",
            return_value=MagicMock(return_value=mock_ctx),
        ),
        patch(
            "backend.application.services.chat_service.SwissMarketService",
            return_value=mock_svc,
        ),
        patch(
            "backend.application.services.chat_service.SQLASwissStockRepository",
        ),
    ):
        result = await _dispatch_tool("search_stocks", {"query": "nestlé"})

    assert isinstance(result, str)
    mock_svc.list_smi_stocks.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_tool_unknown_returns_error() -> None:
    result = await _dispatch_tool("nonexistent_tool", {})
    assert "unbekannt" in result.lower() or "unknown" in result.lower()


def test_chat_message_dataclass() -> None:
    msg = ChatMessage(role="user", content="Hallo")
    assert msg.role == "user"
    assert msg.content == "Hallo"


@pytest.mark.asyncio
async def test_chat_service_build_tool_definitions() -> None:
    svc = ChatService()
    tools = svc._get_tool_definitions()
    assert len(tools) == 6
    names = {t["name"] for t in tools}
    assert "search_stocks" in names
    assert "filter_stocks" in names
    assert "get_factsheet" in names
    assert "get_macro_context" in names
    assert "compare_stocks" in names
    assert "get_ranking" in names


@pytest.mark.asyncio
async def test_get_factsheet_strips_exchange_suffix() -> None:
    """W-15/F-COMM-2: Claude ruft get_factsheet(ticker='NESN.SW') tool-konform auf
    (Tool-Schema schlägt genau dieses Format vor) — der Handler muss das
    Exchange-Suffix vor dem Repository-Lookup entfernen, analog zu
    `stock_service._normalize_ticker` / dem REST-Factsheet-Endpoint."""
    nesn = MagicMock()
    nesn.ticker = "NESN"
    nesn.signal = "BUY"
    nesn.quant_score = 87.5
    nesn.eligible_3a = True

    mock_svc = AsyncMock()
    mock_svc.get_swiss_stock = AsyncMock(return_value=nesn)

    with patch(
        "backend.application.services.chat_service._make_market_svc",
        return_value=mock_svc,
    ):
        result = await _get_factsheet({"ticker": "NESN.SW"}, MagicMock())

    assert "Keine Daten" not in result
    mock_svc.get_swiss_stock.assert_awaited_once_with("NESN")


@pytest.mark.asyncio
async def test_chat_stream_records_cost_after_claude_call() -> None:
    """W-16/F-COMM-3: Nach einem (gemockten) Chat-Claude-Call muss
    CostTracker.record mit feature='chat' aufgerufen werden, sonst fehlt
    der 'chat'-Eintrag im Admin-Cost-Dashboard (GET /api/v1/admin/costs)."""

    final_message = MagicMock()
    final_message.stop_reason = "end_turn"
    final_message.content = []
    final_message.id = "msg_test_123"
    final_message.usage = MagicMock(input_tokens=120, output_tokens=45)

    async def _empty_aiter() -> AsyncIterator[None]:
        return
        yield  # pragma: no cover - makes this an async generator function

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_stream_ctx.__aiter__ = MagicMock(side_effect=lambda: _empty_aiter())
    mock_stream_ctx.get_final_message = AsyncMock(return_value=final_message)

    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(return_value=mock_stream_ctx)

    mock_cost_tracker = AsyncMock()

    svc = ChatService(cost_tracker=mock_cost_tracker)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        events = [event async for event in svc.stream([ChatMessage(role="user", content="Hi")])]

    assert any('"type": "done"' in e for e in events)
    mock_cost_tracker.record.assert_awaited_once()
    _, kwargs = mock_cost_tracker.record.call_args
    assert kwargs["feature"] == "chat"
    assert kwargs["provider"] == "anthropic"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 45
