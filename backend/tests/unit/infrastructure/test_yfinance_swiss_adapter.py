"""Unit Tests für YFinanceSwissAdapter — yfinance wird vollständig gemockt."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pandas as pd
import pytest

from backend.domain.errors import SwissDataUnavailableError, YahooFinanceBlockedError
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


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_retries_on_transient_error(
    mock_yf: MagicMock, mock_sleep: AsyncMock
) -> None:
    good_ticker_obj = MagicMock()
    good_ticker_obj.info = {"marketCap": 100_000_000}
    mock_yf.Ticker.side_effect = [Exception("network timeout"), good_ticker_obj]

    adapter = YFinanceSwissAdapter()
    result = await adapter.get_fundamentals("NOVN")

    assert result.market_cap_chf == Decimal("100000000")
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_unavailable_error_not_retried(mock_yf: MagicMock, mock_sleep: AsyncMock) -> None:
    mock_yf.Ticker.return_value.info = {}

    adapter = YFinanceSwissAdapter()
    with pytest.raises(SwissDataUnavailableError):
        await adapter.get_fundamentals("UNKNOWN")

    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_isin_returns_none_when_absent(mock_yf: MagicMock) -> None:
    mock_yf.Ticker.return_value.info = {"marketCap": 1_000_000}
    adapter = YFinanceSwissAdapter()
    result = await adapter.get_isin("NOVN")
    assert result is None


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_yahoo_401_raises_blocked_error(
    mock_yf: MagicMock, mock_sleep: AsyncMock
) -> None:
    """Yahoo blockt Render's Cloud-IP-Range mit HTTP 401 'Invalid Crumb'.

    Diese Exception muss in YahooFinanceBlockedError (Subklasse von
    SwissDataUnavailableError) übersetzt werden, statt roh durchzufallen —
    sonst landet sie als raw 500 im REST-Layer.
    """
    mock_yf.Ticker.side_effect = Exception('401 Client Error: Unauthorized — "Invalid Crumb"')

    adapter = YFinanceSwissAdapter()
    with pytest.raises(YahooFinanceBlockedError) as exc_info:
        await adapter.get_fundamentals("NESN")

    assert isinstance(exc_info.value, SwissDataUnavailableError)
    assert "NESN" in str(exc_info.value)


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_price_history_yahoo_block_raises_blocked_error(
    mock_yf: MagicMock, mock_sleep: AsyncMock
) -> None:
    mock_yf.Ticker.return_value.history.side_effect = Exception("HTTP Error 401: Unauthorized")

    adapter = YFinanceSwissAdapter()
    with pytest.raises(YahooFinanceBlockedError):
        await adapter.get_price_history("NESN", days=30)


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_dividends_yahoo_block_raises_blocked_error(
    mock_yf: MagicMock, mock_sleep: AsyncMock
) -> None:
    """_sync_dividends liest .dividends als Property — PropertyMock simuliert das."""
    mock_yf.Ticker.return_value.info = {"marketCap": 1_000_000}
    type(mock_yf.Ticker.return_value).dividends = PropertyMock(
        side_effect=Exception("Invalid Crumb")
    )

    adapter = YFinanceSwissAdapter()
    with pytest.raises(YahooFinanceBlockedError):
        await adapter.get_dividends("NESN")


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_yahoo_rate_limit_raises_blocked_error(
    mock_yf: MagicMock, mock_sleep: AsyncMock
) -> None:
    """Yahoo drosselt mit YFRateLimitError (429) — eigene Exception-Klasse,

    deren Message ("Too Many Requests. Rate limited. Try after a while.")
    keines der ursprünglichen String-Substrings ("401", "invalid crumb",
    "unauthorized") enthält. Muss per isinstance-Check erkannt werden, sonst
    fällt sie als raw 500 durch (separater Production-Vorfall vom 16.06.2026).
    """
    from yfinance.exceptions import YFRateLimitError

    mock_yf.Ticker.side_effect = YFRateLimitError()

    adapter = YFinanceSwissAdapter()
    with pytest.raises(YahooFinanceBlockedError) as exc_info:
        await adapter.get_fundamentals("NESN")

    assert isinstance(exc_info.value, SwissDataUnavailableError)


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.yfinance_swiss.asyncio.sleep", new_callable=AsyncMock)
@patch("backend.infrastructure.adapters.yfinance_swiss.yf")
async def test_get_fundamentals_generic_error_not_translated(
    mock_yf: MagicMock, mock_sleep: AsyncMock
) -> None:
    """Nicht-Yahoo-Block-Fehler (z.B. Netzwerk-Timeout) bleiben unverändert."""
    mock_yf.Ticker.side_effect = Exception("network timeout")

    adapter = YFinanceSwissAdapter()
    with pytest.raises(Exception) as exc_info:
        await adapter.get_fundamentals("NESN")

    assert not isinstance(exc_info.value, SwissDataUnavailableError)
    assert "network timeout" in str(exc_info.value)
