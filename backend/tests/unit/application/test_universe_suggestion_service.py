"""Unit-Tests für UniverseSuggestionService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.services.universe_suggestion_service import (
    EmptySuggestion,
    UniverseSuggestionService,
)
from backend.domain.entities.stock import Stock

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_stock(ticker: str, name: str = "Test", sector: str = "Tech") -> Stock:
    return Stock(
        id=uuid.uuid4(),
        ticker=ticker,
        name=f"{name} {ticker}",
        sector=sector,
        currency="USD",
    )


def _fake_llm_response(name: str, region: str, tickers: list[str], reasoning: str) -> MagicMock:
    """Mockt eine Anthropic-Tool-Use-Response."""
    response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "submit_universe_suggestion"
    tool_block.input = {
        "name": name,
        "region": region,
        "tickers": tickers,
        "reasoning": reasoning,
    }
    response.content = [tool_block]
    return response


class TestUniverseSuggestionService:
    async def test_suggest_returns_valid_universe_with_filtered_tickers(self) -> None:
        """LLM-Output passt zum Katalog — alle Tickers werden zurückgegeben."""
        stocks = [_make_stock("AAPL"), _make_stock("MSFT"), _make_stock("NVDA")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Tech-Top-3",
                region="US",
                tickers=["AAPL", "MSFT", "NVDA"],
                reasoning="US-Tech-Schwergewichte mit starker Marge.",
            )
        )

        service = UniverseSuggestionService(llm_client=llm_client, stock_service=stock_service)
        suggestion = await service.suggest(description="Tech-Heavy USA")

        assert suggestion.name == "Tech-Top-3"
        assert suggestion.region == "US"
        assert suggestion.tickers == ["AAPL", "MSFT", "NVDA"]
        assert "Tech" in suggestion.reasoning
        assert llm_client.messages_create.call_count == 1

    async def test_suggest_filters_unknown_tickers(self) -> None:
        """Tickers außerhalb des Katalogs werden rausgefiltert."""
        stocks = [_make_stock("AAPL"), _make_stock("MSFT")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Mix",
                region="US",
                tickers=["AAPL", "FOO", "MSFT", "BAR"],
                reasoning="Test mit unbekannten Tickers.",
            )
        )

        service = UniverseSuggestionService(llm_client=llm_client, stock_service=stock_service)
        suggestion = await service.suggest(description="Test")

        assert suggestion.tickers == ["AAPL", "MSFT"]

    async def test_suggest_raises_empty_when_less_than_two_valid_tickers(self) -> None:
        """Wenn nach Filterung weniger als 2 Tickers übrig → EmptySuggestion."""
        stocks = [_make_stock("AAPL")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Solo",
                region="US",
                tickers=["FOO", "BAR"],
                reasoning="Test mit unbekannten Tickers, keine Treffer.",
            )
        )

        service = UniverseSuggestionService(llm_client=llm_client, stock_service=stock_service)

        with pytest.raises(EmptySuggestion):
            await service.suggest(description="Test")

    async def test_suggest_uses_haiku_model(self) -> None:
        """Service muss claude-haiku-4-5 verwenden."""
        stocks = [_make_stock("AAPL"), _make_stock("MSFT")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Test",
                region="US",
                tickers=["AAPL", "MSFT"],
                reasoning="Qualitätsaktien mit solidem Fundament.",
            )
        )

        service = UniverseSuggestionService(llm_client=llm_client, stock_service=stock_service)
        await service.suggest(description="Test")

        call_kwargs = llm_client.messages_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        assert call_kwargs["feature"] == "universe_suggestion"
