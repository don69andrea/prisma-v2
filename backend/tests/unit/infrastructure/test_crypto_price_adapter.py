"""Unit Tests für CryptoPriceAdapter — yfinance wird vollständig gemockt.

Test-First (TDD / RED-Phase):
- Spaltenumbenennung (Open→open, High→high, Low→low, Close→close, Volume→volume)
- Symbol-Spalte wird hinzugefügt
- Retry bei Netzwerkfehler (max 2 Retries)
- Coverage-Check: ValueError bei weniger als 200 Zeilen
- Coverage-Check: ValueError bei Lücken > 3 Handelstage
- asyncio.to_thread wird korrekt verwendet (kein run_in_executor)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


def _make_ohlcv_df(n: int = 250, symbol: str = "BTC-USD") -> pd.DataFrame:
    """Hilfsfunktion: erstellt einen DataFrame mit OHLCV-Daten wie yfinance sie liefert."""
    idx = pd.bdate_range(start="2017-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": [10000.0 + i for i in range(n)],
            "High": [10100.0 + i for i in range(n)],
            "Low": [9900.0 + i for i in range(n)],
            "Close": [10050.0 + i for i in range(n)],
            "Volume": [1_000_000 + i * 100 for i in range(n)],
            "Adj Close": [10050.0 + i for i in range(n)],
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# Tests: Spaltenumbenennung + Symbol-Spalte
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_column_mapping(mock_yf: MagicMock) -> None:
    """Adapter muss yfinance-Spalten korrekt umbenennen und symbol-Spalte hinzufügen."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    mock_yf.download.return_value = _make_ohlcv_df(250, "BTC-USD")
    adapter = CryptoPriceAdapter()
    df = await adapter.fetch_ohlcv("BTC-USD")

    assert "open" in df.columns, "Spalte 'open' fehlt"
    assert "high" in df.columns, "Spalte 'high' fehlt"
    assert "low" in df.columns, "Spalte 'low' fehlt"
    assert "close" in df.columns, "Spalte 'close' fehlt"
    assert "volume" in df.columns, "Spalte 'volume' fehlt"
    assert "symbol" in df.columns, "Spalte 'symbol' fehlt"


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_symbol_value(mock_yf: MagicMock) -> None:
    """Adapter muss das übergebene Symbol in der symbol-Spalte speichern."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    mock_yf.download.return_value = _make_ohlcv_df(250, "ETH-USD")
    adapter = CryptoPriceAdapter()
    df = await adapter.fetch_ohlcv("ETH-USD")

    assert all(df["symbol"] == "ETH-USD"), "symbol-Spalte hat falschen Wert"


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_no_uppercase_columns(mock_yf: MagicMock) -> None:
    """Nach dem Mapping dürfen keine ursprünglichen Grossbuchstaben-Spalten mehr vorhanden sein."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    mock_yf.download.return_value = _make_ohlcv_df(250)
    adapter = CryptoPriceAdapter()
    df = await adapter.fetch_ohlcv("BTC-USD")

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        assert col not in df.columns, f"Original-Spalte '{col}' wurde nicht umbenannt"


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_date_index_or_column(mock_yf: MagicMock) -> None:
    """Adapter muss eine 'date'-Spalte oder einen date-Index liefern."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    mock_yf.download.return_value = _make_ohlcv_df(250)
    adapter = CryptoPriceAdapter()
    df = await adapter.fetch_ohlcv("BTC-USD")

    has_date = "date" in df.columns or df.index.name == "date"
    assert has_date, "Kein 'date' als Spalte oder Index vorhanden"


# ---------------------------------------------------------------------------
# Tests: asyncio.to_thread Nutzung
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.asyncio")
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_uses_asyncio_to_thread(
    mock_yf: MagicMock, mock_asyncio: MagicMock
) -> None:
    """Adapter muss asyncio.to_thread verwenden (nicht run_in_executor)."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    # to_thread muss den rohen yfinance DataFrame zurückgeben
    raw_df = _make_ohlcv_df(250)
    mock_asyncio.to_thread = AsyncMock(return_value=raw_df)
    mock_asyncio.sleep = AsyncMock()

    adapter = CryptoPriceAdapter()
    await adapter.fetch_ohlcv("BTC-USD")

    mock_asyncio.to_thread.assert_called()


# ---------------------------------------------------------------------------
# Tests: Retry-Logik
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.asyncio")
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_retries_on_network_error(
    mock_yf: MagicMock, mock_asyncio: MagicMock
) -> None:
    """Adapter muss bei Netzwerkfehler maximal 2x neu versuchen."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    raw_df = _make_ohlcv_df(250)
    mock_asyncio.to_thread = AsyncMock(
        side_effect=[
            ConnectionError("network error"),
            ConnectionError("network error"),
            raw_df,
        ]
    )
    mock_asyncio.sleep = AsyncMock()

    adapter = CryptoPriceAdapter()
    df = await adapter.fetch_ohlcv("BTC-USD")

    assert not df.empty
    assert mock_asyncio.to_thread.call_count == 3  # 2 Fehler + 1 Erfolg


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.asyncio")
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_raises_after_max_retries(
    mock_yf: MagicMock, mock_asyncio: MagicMock
) -> None:
    """Adapter muss nach 2 Retries die Exception weiterwerfen."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    mock_asyncio.to_thread = AsyncMock(side_effect=ConnectionError("persistent error"))
    mock_asyncio.sleep = AsyncMock()

    adapter = CryptoPriceAdapter()
    with pytest.raises(ConnectionError, match="persistent error"):
        await adapter.fetch_ohlcv("BTC-USD")

    # _RETRIES = 2 → 3 Versuche total (0, 1, 2)
    assert mock_asyncio.to_thread.call_count == 3


@pytest.mark.asyncio
@patch("backend.infrastructure.adapters.crypto_price_adapter.asyncio")
@patch("backend.infrastructure.adapters.crypto_price_adapter.yfinance")
async def test_fetch_ohlcv_retry_uses_exponential_backoff(
    mock_yf: MagicMock, mock_asyncio: MagicMock
) -> None:
    """Adapter muss bei Retries exponentielles Backoff verwenden (1.0, 2.0 Sekunden)."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    raw_df = _make_ohlcv_df(250)
    mock_asyncio.to_thread = AsyncMock(
        side_effect=[ConnectionError("err1"), ConnectionError("err2"), raw_df]
    )
    mock_asyncio.sleep = AsyncMock()

    adapter = CryptoPriceAdapter()
    await adapter.fetch_ohlcv("BTC-USD")

    # 2 Retries → 2 sleep-Aufrufe mit 1.0 und 2.0
    assert mock_asyncio.sleep.call_count == 2
    calls = [c.args[0] for c in mock_asyncio.sleep.call_args_list]
    assert calls[0] == pytest.approx(1.0), f"Erster Sleep soll 1.0s sein, war {calls[0]}"
    assert calls[1] == pytest.approx(2.0), f"Zweiter Sleep soll 2.0s sein, war {calls[1]}"


# ---------------------------------------------------------------------------
# Tests: Coverage-Validierung
# ---------------------------------------------------------------------------


def test_validate_coverage_ok() -> None:
    """validate_coverage muss bei ausreichend Zeilen ohne Fehler durchlaufen."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    adapter = CryptoPriceAdapter()
    df = _make_ohlcv_df(250)
    # Soll keinen Fehler werfen
    adapter.validate_coverage(df)


def test_validate_coverage_too_few_rows_raises() -> None:
    """validate_coverage muss ValueError werfen wenn weniger als 200 Zeilen vorhanden."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    adapter = CryptoPriceAdapter()
    df = _make_ohlcv_df(150)

    with pytest.raises(ValueError, match="200"):
        adapter.validate_coverage(df)


def test_validate_coverage_gap_too_large_raises() -> None:
    """validate_coverage muss ValueError werfen wenn Lücke > 3 Handelstage vorhanden."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    adapter = CryptoPriceAdapter()

    # 200 Zeilen, aber mit einer Lücke von 10 Tagen in der Mitte
    idx_part1 = pd.bdate_range(start="2020-01-01", periods=100, freq="B")
    idx_part2 = pd.bdate_range(start="2020-06-01", periods=100, freq="B")  # grosse Lücke
    idx = idx_part1.append(idx_part2)

    df = pd.DataFrame(
        {"Close": [1.0] * 200},
        index=idx,
    )

    with pytest.raises(ValueError, match="[Ll]ücke|gap"):
        adapter.validate_coverage(df)


def test_validate_coverage_exactly_200_rows_ok() -> None:
    """validate_coverage muss bei genau 200 Zeilen durchlaufen (Grenzfall)."""
    from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

    adapter = CryptoPriceAdapter()
    df = _make_ohlcv_df(200)
    # Soll keinen Fehler werfen
    adapter.validate_coverage(df)
