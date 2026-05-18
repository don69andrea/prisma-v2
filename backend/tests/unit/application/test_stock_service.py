"""Unit-Tests für StockService mit gemocktem Repository."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.services.stock_service import StockService
from backend.domain.entities.stock import Stock
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider

pytestmark = pytest.mark.unit


def _make_stock(ticker: str) -> Stock:
    return Stock(
        id=uuid.uuid4(),
        ticker=ticker,
        name=f"{ticker} Corp",
        currency="USD",
    )


def _make_service(stocks: list[Stock] | None = None) -> tuple[StockService, AsyncMock]:
    """Hilfsfunktion: erzeugt StockService + gemocktes Repository."""
    mock_repo = MagicMock()
    mock_repo.list = AsyncMock(return_value=stocks or [])
    service = StockService(repository=mock_repo, market_data_provider=StubMarketDataProvider())
    return service, mock_repo


class TestListStocks:
    async def test_delegates_to_repository(self) -> None:
        expected = [_make_stock("AAPL"), _make_stock("MSFT")]
        service, mock_repo = _make_service(expected)

        result = await service.list_stocks(limit=10, offset=0)

        mock_repo.list.assert_called_once_with(limit=10, offset=0)
        assert result == expected

    async def test_uses_default_limit(self) -> None:
        service, mock_repo = _make_service()
        await service.list_stocks()
        mock_repo.list.assert_called_once_with(limit=50, offset=0)

    async def test_passes_offset_to_repository(self) -> None:
        service, mock_repo = _make_service()
        await service.list_stocks(limit=10, offset=30)
        mock_repo.list.assert_called_once_with(limit=10, offset=30)

    async def test_returns_empty_list_when_repository_is_empty(self) -> None:
        service, _ = _make_service([])
        result = await service.list_stocks()
        assert result == []


class TestPaginationValidation:
    async def test_limit_zero_raises(self) -> None:
        service, _ = _make_service()
        with pytest.raises(ValueError, match="limit"):
            await service.list_stocks(limit=0)

    async def test_limit_above_max_raises(self) -> None:
        service, _ = _make_service()
        with pytest.raises(ValueError, match="limit"):
            await service.list_stocks(limit=201)

    async def test_limit_at_max_is_allowed(self) -> None:
        service, mock_repo = _make_service()
        await service.list_stocks(limit=200)
        mock_repo.list.assert_called_once_with(limit=200, offset=0)

    async def test_negative_offset_raises(self) -> None:
        service, _ = _make_service()
        with pytest.raises(ValueError, match="offset"):
            await service.list_stocks(offset=-1)

    async def test_zero_offset_is_allowed(self) -> None:
        service, mock_repo = _make_service()
        await service.list_stocks(offset=0)
        mock_repo.list.assert_called_once_with(limit=50, offset=0)
