"""Unit-Tests für ChatService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.application.services.chat_service import ChatMessage, ChatService, _dispatch_tool

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
