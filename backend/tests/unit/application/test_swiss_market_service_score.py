"""Tests für SwissMarketService.score_stock()."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore

pytestmark = pytest.mark.unit


def _make_nesn() -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker="NESN",
        isin="CH0038863350",
        name="Nestlé SA",
        exchange="XSWX",
        sector="Consumer Staples",
        market_cap_chf=Decimal("280000000000"),
    )


@pytest.mark.asyncio
async def test_score_stock_returns_quant_score() -> None:
    mock_repo = AsyncMock()
    mock_market_data = AsyncMock()
    mock_repo.get_by_ticker.return_value = _make_nesn()
    mock_market_data.get_fundamentals.return_value = SwissFundamentals(
        market_cap_chf=Decimal("280000000000"),
        pe_ratio=18.0,
        pb_ratio=3.0,
        dividend_yield=0.027,
        eps_chf=5.4,
    )

    service = SwissMarketService(repo=mock_repo, market_data=mock_market_data)
    result = await service.score_stock("NESN")

    assert isinstance(result, SwissQuantScore)
    assert result.ticker == "NESN"
    assert result.signal in ("BUY", "HOLD")
    mock_market_data.get_fundamentals.assert_called_once_with("NESN")


@pytest.mark.asyncio
async def test_score_stock_raises_when_not_found() -> None:
    mock_repo = AsyncMock()
    mock_market_data = AsyncMock()
    mock_repo.get_by_ticker.return_value = None

    service = SwissMarketService(repo=mock_repo, market_data=mock_market_data)

    with pytest.raises(ValueError, match="nicht gefunden"):
        await service.score_stock("UNKNOWN")

    mock_market_data.get_fundamentals.assert_not_called()
