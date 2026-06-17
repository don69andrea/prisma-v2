"""Unit-Tests für ChatService — inkl. BUG-01/02 Regression Tests."""

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


# ---------------------------------------------------------------------------
# BUG-01 Regression: ChatService darf kein eigenes AsyncAnthropic() erstellen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_service_uses_injected_raw_client_not_own_anthropic() -> None:
    """BUG-01: ChatService darf anthropic.AsyncAnthropic() NICHT selbst aufrufen.
    Der per DI injizierte LLMClient (raw_client) muss verwendet werden."""
    mock_anthropic_client = MagicMock()
    mock_llm = MagicMock()
    mock_llm.raw_client = mock_anthropic_client
    mock_llm._cost_tracker = AsyncMock()

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.content = []
    final_msg.id = "msg_test"
    final_msg.usage = MagicMock(input_tokens=10, output_tokens=5)

    async def _empty() -> AsyncIterator[None]:
        return
        yield  # pragma: no cover

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.__aiter__ = MagicMock(side_effect=lambda: _empty())
    stream_ctx.get_final_message = AsyncMock(return_value=final_msg)

    mock_anthropic_client.messages.stream = MagicMock(return_value=stream_ctx)

    svc = ChatService(llm_client=mock_llm)

    with patch("anthropic.AsyncAnthropic") as mock_ctor:
        _ = [e async for e in svc.stream([ChatMessage(role="user", content="Test")])]

    mock_ctor.assert_not_called()
    mock_anthropic_client.messages.stream.assert_called_once()


@pytest.mark.asyncio
async def test_chat_service_without_llm_client_raises_on_stream() -> None:
    """ChatService ohne llm_client muss stream() mit RuntimeError ablehnen
    statt still ein eigenes SDK-Objekt zu erstellen."""
    svc = ChatService()
    events = [e async for e in svc.stream([ChatMessage(role="user", content="x")])]
    # Muss einen Error-Event liefern, nicht crashen / kein SDK-Aufruf
    assert any("error" in e for e in events)


# ---------------------------------------------------------------------------
# BUG-02 Regression: Continuation-Call muss tools= enthalten
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_continuation_stream_includes_tools_parameter() -> None:
    """BUG-02: Der zweite Stream-Call nach tool_use muss tools= enthalten,
    damit Claude in der Continuation weitere Tools aufrufen kann."""
    mock_anthropic_client = MagicMock()
    mock_llm = MagicMock()
    mock_llm.raw_client = mock_anthropic_client
    mock_llm._cost_tracker = AsyncMock()

    # --- Erster Stream-Call: tool_use ---
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_stocks"
    tool_block.id = "tu_001"
    tool_block.input = {"query": "NESN"}

    first_msg = MagicMock()
    first_msg.stop_reason = "tool_use"
    first_msg.content = [tool_block]
    first_msg.id = "msg_1"
    first_msg.usage = MagicMock(input_tokens=50, output_tokens=12)

    async def _first_events() -> AsyncIterator[object]:
        evt = MagicMock()
        evt.type = "content_block_start"
        evt.content_block = MagicMock()
        evt.content_block.type = "tool_use"
        evt.content_block.name = "search_stocks"
        evt.content_block.id = "tu_001"
        yield evt

    first_ctx = AsyncMock()
    first_ctx.__aenter__ = AsyncMock(return_value=first_ctx)
    first_ctx.__aexit__ = AsyncMock(return_value=False)
    first_ctx.__aiter__ = MagicMock(side_effect=lambda: _first_events())
    first_ctx.get_final_message = AsyncMock(return_value=first_msg)

    # --- Zweiter Stream-Call: end_turn ---
    second_msg = MagicMock()
    second_msg.stop_reason = "end_turn"
    second_msg.content = []
    second_msg.id = "msg_2"
    second_msg.usage = MagicMock(input_tokens=80, output_tokens=30)

    async def _second_events() -> AsyncIterator[object]:
        evt = MagicMock()
        evt.type = "content_block_delta"
        evt.delta = MagicMock()
        evt.delta.text = "Hier ist NESN."
        yield evt

    second_ctx = AsyncMock()
    second_ctx.__aenter__ = AsyncMock(return_value=second_ctx)
    second_ctx.__aexit__ = AsyncMock(return_value=False)
    second_ctx.__aiter__ = MagicMock(side_effect=lambda: _second_events())
    second_ctx.get_final_message = AsyncMock(return_value=second_msg)

    call_count = 0

    def _make_stream(**kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return first_ctx if call_count == 1 else second_ctx

    mock_anthropic_client.messages.stream = MagicMock(side_effect=_make_stream)

    svc = ChatService(llm_client=mock_llm)

    with patch(
        "backend.application.services.chat_service._dispatch_tool",
        return_value='{"ticker": "NESN", "signal": "BUY"}',
    ):
        _ = [e async for e in svc.stream([ChatMessage(role="user", content="NESN suchen")])]

    assert call_count == 2, "Zweiter Stream-Call (Continuation) wurde nie ausgeführt"
    second_call_kwargs = mock_anthropic_client.messages.stream.call_args_list[1].kwargs
    assert "tools" in second_call_kwargs, (
        "BUG-02: tools= fehlt im zweiten Stream-Call → Claude kann keine weiteren "
        "Tools aufrufen. Fix: tools=cast(Any, _TOOL_DEFINITIONS) ergänzen."
    )


@pytest.mark.asyncio
async def test_chat_stream_records_cost_via_llm_client_cost_tracker() -> None:
    """W-16/F-COMM-3 (updated): Cost-Tracking muss via LLMClient._cost_tracker laufen,
    nicht via eigenem CostTracker-Feld."""
    mock_anthropic_client = MagicMock()
    mock_cost_tracker = AsyncMock()
    mock_llm = MagicMock()
    mock_llm.raw_client = mock_anthropic_client
    mock_llm._cost_tracker = mock_cost_tracker

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.content = []
    final_msg.id = "msg_xyz"
    final_msg.usage = MagicMock(input_tokens=120, output_tokens=45)

    async def _empty() -> AsyncIterator[None]:
        return
        yield  # pragma: no cover

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.__aiter__ = MagicMock(side_effect=lambda: _empty())
    stream_ctx.get_final_message = AsyncMock(return_value=final_msg)
    mock_anthropic_client.messages.stream = MagicMock(return_value=stream_ctx)

    svc = ChatService(llm_client=mock_llm)
    events = [e async for e in svc.stream([ChatMessage(role="user", content="Hi")])]

    assert any('"type": "done"' in e for e in events)
    mock_cost_tracker.record.assert_awaited_once()
    _, kwargs = mock_cost_tracker.record.call_args
    assert kwargs["feature"] == "chat"
    assert kwargs["provider"] == "anthropic"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 45


# ---------------------------------------------------------------------------
# Bestehende Tests (unverändert)
# ---------------------------------------------------------------------------


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
    """W-15/F-COMM-2: Claude ruft get_factsheet(ticker='NESN.SW') tool-konform auf."""
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
