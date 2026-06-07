"""Unit-Tests für SwissMarketService mit gemocktem Repository."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.entities.swiss_stock import SwissStock

pytestmark = pytest.mark.unit


def _make_stock(ticker: str) -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker=ticker,
        isin="CH0038863350",
        name=f"{ticker} AG",
        exchange="XSWX",
        sector="Financials",
        market_cap_chf=None,
    )


def _make_service(stocks: list[SwissStock] | None = None) -> tuple[SwissMarketService, MagicMock]:
    mock_repo = MagicMock()
    mock_repo.list_by_exchange = AsyncMock(return_value=stocks or [])
    mock_repo.get_by_ticker = AsyncMock(return_value=None)
    service = SwissMarketService(repo=mock_repo)
    return service, mock_repo


class TestListSmiStocks:
    async def test_delegates_to_repo_with_xswx(self) -> None:
        stocks = [_make_stock("NESN"), _make_stock("NOVN")]
        service, mock_repo = _make_service(stocks)

        result = await service.list_smi_stocks()

        mock_repo.list_by_exchange.assert_called_once_with(exchange="XSWX")
        assert result == stocks

    async def test_returns_empty_list_when_no_stocks(self) -> None:
        service, _ = _make_service([])
        result = await service.list_smi_stocks()
        assert result == []


class TestGetSwissStock:
    async def test_returns_stock_when_found(self) -> None:
        stock = _make_stock("NESN")
        service, mock_repo = _make_service()
        mock_repo.get_by_ticker = AsyncMock(return_value=stock)

        result = await service.get_swiss_stock("nesn")

        mock_repo.get_by_ticker.assert_called_once_with("NESN")
        assert result == stock

    async def test_returns_none_when_not_found(self) -> None:
        service, mock_repo = _make_service()
        mock_repo.get_by_ticker = AsyncMock(return_value=None)

        result = await service.get_swiss_stock("FAKE")

        assert result is None

    async def test_uppercases_ticker(self) -> None:
        service, mock_repo = _make_service()
        await service.get_swiss_stock("nesn")
        mock_repo.get_by_ticker.assert_called_once_with("NESN")
