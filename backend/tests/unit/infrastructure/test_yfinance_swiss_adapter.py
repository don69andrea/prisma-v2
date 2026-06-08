"""Unit Tests für YFinanceSwissAdapter — yfinance wird vollständig gemockt."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.domain.errors import SwissDataUnavailableError
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

pytestmark = pytest.mark.unit


def test_build_yf_ticker_uppercases_and_adds_suffix() -> None:
    adapter = YFinanceSwissAdapter()
    assert adapter.build_yf_ticker("novn") == "NOVN.SW"
    assert adapter.build_yf_ticker("NESN") == "NESN.SW"


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_ok(mock_yf: MagicMock) -> None:
    mock_yf.Ticker.return_value.info = {
        "marketCap": 250_000_000_000,
        "trailingPE": 22.5,
        "priceToBook": 3.2,
        "dividendYield": 0.027,
        "trailingEps": 5.4,
    }
    adapter = YFinanceSwissAdapter()
    result = await adapter.get_fundamentals("NESN")

    assert isinstance(result, SwissFundamentals)
    assert result.market_cap_chf == Decimal("250000000000")
    assert result.pe_ratio == 22.5
    assert result.pb_ratio == 3.2
    mock_yf.Ticker.assert_called_once_with("NESN.SW")


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_empty_info_raises(mock_yf: MagicMock) -> None:
    mock_yf.Ticker.return_value.info = {}
    adapter = YFinanceSwissAdapter()

    with pytest.raises(SwissDataUnavailableError) as exc_info:
        await adapter.get_fundamentals("UNKNOWN")
    assert "UNKNOWN" in str(exc_info.value)


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_partial_data(mock_yf: MagicMock) -> None:
    mock_yf.Ticker.return_value.info = {"marketCap": 10_000_000_000}
    adapter = YFinanceSwissAdapter()
    result = await adapter.get_fundamentals("ZURN")

    assert result.market_cap_chf == Decimal("10000000000")
    assert result.pe_ratio is None
    assert result.dividend_yield is None


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_price_history_ok(mock_yf: MagicMock) -> None:
    mock_df = pd.DataFrame(
        {"Close": [102.5, 103.0], "Volume": [500_000, 600_000]},
        index=pd.to_datetime(["2026-01-02", "2026-01-03"], utc=True),
    )
    mock_yf.Ticker.return_value.history.return_value = mock_df
    adapter = YFinanceSwissAdapter()
    result = await adapter.get_price_history("NESN", days=2)

    assert list(result.columns) == ["Close", "Volume"]
    assert len(result) == 2
    mock_yf.Ticker.return_value.history.assert_called_once_with(period="2d")


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_price_history_empty_returns_empty_df(mock_yf: MagicMock) -> None:
    mock_yf.Ticker.return_value.history.return_value = pd.DataFrame()
    adapter = YFinanceSwissAdapter()
    result = await adapter.get_price_history("STMN", days=30)

    assert isinstance(result, pd.DataFrame)
    assert result.empty


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_isin(mock_yf: MagicMock) -> None:
    mock_yf.Ticker.return_value.info = {
        "isin": "CH0038863350",
        "marketCap": 200_000_000_000,
    }
    adapter = YFinanceSwissAdapter()
    result = await adapter.get_isin("NESN")

    assert result == "CH0038863350"
