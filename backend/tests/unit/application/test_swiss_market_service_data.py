"""Tests für SwissMarketService.refresh_market_data()."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

pytestmark = pytest.mark.unit


def _make_nesn() -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker="NESN",
        isin="CH0038863350",
        name="Nestlé SA",
        exchange="XSWX",
        sector="Consumer Staples",
        market_cap_chf=None,
    )


@pytest.mark.asyncio
async def test_refresh_market_data_updates_market_cap() -> None:
    mock_repo = AsyncMock()
    mock_market_data = AsyncMock()

    nesn = _make_nesn()
    mock_repo.get_by_ticker.return_value = nesn
    mock_market_data.get_fundamentals.return_value = SwissFundamentals(
        market_cap_chf=Decimal("280000000000"),
        pe_ratio=25.0,
        pb_ratio=None,
        dividend_yield=0.028,
        eps_chf=None,
    )

    service = SwissMarketService(repo=mock_repo, market_data=mock_market_data)
    result = await service.refresh_market_data("NESN")

    assert result.market_cap_chf == Decimal("280000000000")
    mock_repo.get_by_ticker.assert_called_once_with("NESN")
    mock_repo.upsert_batch.assert_called_once()
    upserted = mock_repo.upsert_batch.call_args[0][0][0]
    assert upserted.market_cap_chf == Decimal("280000000000")


@pytest.mark.asyncio
async def test_refresh_market_data_raises_when_stock_not_found() -> None:
    mock_repo = AsyncMock()
    mock_market_data = AsyncMock()
    mock_repo.get_by_ticker.return_value = None

    service = SwissMarketService(repo=mock_repo, market_data=mock_market_data)

    with pytest.raises(ValueError, match="nicht gefunden"):
        await service.refresh_market_data("UNKNOWN")

    mock_market_data.get_fundamentals.assert_not_called()
