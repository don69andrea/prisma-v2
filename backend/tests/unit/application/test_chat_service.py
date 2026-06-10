"""Unit-Tests für ChatService."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.application.services.chat_service import ChatMessage, ChatService, _dispatch_tool

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_dispatch_tool_search_stocks() -> None:
    mock_stock_service = AsyncMock()
    mock_stock_service.search.return_value = []

    with patch(
        "backend.application.services.chat_service._get_stock_service",
        return_value=mock_stock_service,
    ):
        result = await _dispatch_tool("search_stocks", {"query": "Nestlé"})

    mock_stock_service.search.assert_called_once_with("Nestlé")
    assert isinstance(result, str)


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
