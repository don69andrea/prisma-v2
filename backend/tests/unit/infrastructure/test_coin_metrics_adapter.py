"""Unit Tests für CoinMetricsAdapter — httpx wird vollständig gemockt.

Test-First (TDD / RED-Phase):
- Korrekte URL-Konstruktion (community-api.coinmetrics.io)
- Korrekte Metriken in Request-Params
- Feldmapping: SplyMVRVCur→mvrv_z, RealizedCap→realized_cap,
               AdrActCnt→active_addresses, FlowOutExNtv-FlowInExNtv→exchange_netflow
- NULL-Fallback wenn Coin keine Daten hat (kein ValueError)
- Retry-Logik: max 2 Retries, Exponential Backoff
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_SAMPLE_RESPONSE = {
    "data": [
        {
            "asset": "btc",
            "time": "2024-01-01T00:00:00.000000000Z",
            "SplyMVRVCur": "2.5",
            "RealizedCap": "500000000000",
            "AdrActCnt": "900000",
            "FlowOutExNtv": "10000",
            "FlowInExNtv": "9000",
        },
        {
            "asset": "btc",
            "time": "2024-01-02T00:00:00.000000000Z",
            "SplyMVRVCur": "2.6",
            "RealizedCap": "510000000000",
            "AdrActCnt": "920000",
            "FlowOutExNtv": "12000",
            "FlowInExNtv": "8000",
        },
    ]
}

_EMPTY_RESPONSE: dict[str, Any] = {"data": []}


def _make_mock_response(json_data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Erstellt einen Mock für eine httpx-Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: URL-Konstruktion und Params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_onchain_url_construction() -> None:
    """Adapter muss die korrekte Coin Metrics Community-API URL verwenden."""
    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = CoinMetricsAdapter()
        await adapter.fetch_onchain(["btc"], start="2024-01-01")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        assert "community-api.coinmetrics.io" in url
        assert "/v4/timeseries/asset-metrics" in url


@pytest.mark.asyncio
async def test_fetch_onchain_request_params() -> None:
    """Adapter muss alle erforderlichen Metriken in den Request-Params übergeben."""
    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = CoinMetricsAdapter()
        await adapter.fetch_onchain(["btc", "eth"], start="2024-01-01")

        call_kwargs = mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})

        # assets müssen kommagetrennt sein
        assert "btc" in params.get("assets", "")
        assert "eth" in params.get("assets", "")
        # Alle vier Metriken müssen vorhanden sein
        metrics = params.get("metrics", "")
        assert "RealizedCap" in metrics
        assert "SplyMVRVCur" in metrics
        assert "AdrActCnt" in metrics
        assert "FlowOutExNtv" in metrics
        assert "FlowInExNtv" in metrics
        # Frequenz 1d
        assert params.get("frequency") == "1d"
        # Start-Zeit
        assert params.get("start_time") == "2024-01-01"


# ---------------------------------------------------------------------------
# Tests: Feldmapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_onchain_field_mapping() -> None:
    """Adapter muss Coin-Metrics-Felder korrekt auf interne Spaltennamen mappen."""
    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = CoinMetricsAdapter()
        df = await adapter.fetch_onchain(["btc"], start="2024-01-01")

    # Spalten müssen vorhanden sein
    assert "mvrv_z" in df.columns, "SplyMVRVCur muss auf mvrv_z gemappt werden"
    assert "realized_cap" in df.columns, "RealizedCap muss auf realized_cap gemappt werden"
    assert "active_addresses" in df.columns, "AdrActCnt muss auf active_addresses gemappt werden"
    assert "exchange_netflow" in df.columns, (
        "FlowOut-FlowIn muss auf exchange_netflow gemappt werden"
    )

    # Werte prüfen (erste Zeile)
    first_row = df.iloc[0]
    assert abs(first_row["mvrv_z"] - 2.5) < 1e-9
    assert abs(first_row["realized_cap"] - 500_000_000_000) < 1.0
    assert abs(first_row["active_addresses"] - 900_000) < 1.0
    # exchange_netflow = FlowOutExNtv - FlowInExNtv = 10000 - 9000 = 1000
    assert abs(first_row["exchange_netflow"] - 1000.0) < 1e-9


@pytest.mark.asyncio
async def test_fetch_onchain_date_column() -> None:
    """DataFrame muss eine 'date'-Spalte mit datetime.date-Typen enthalten."""
    from datetime import date

    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = CoinMetricsAdapter()
        df = await adapter.fetch_onchain(["btc"], start="2024-01-01")

    assert "date" in df.columns
    assert df.iloc[0]["date"] == date(2024, 1, 1)
    assert df.iloc[1]["date"] == date(2024, 1, 2)


# ---------------------------------------------------------------------------
# Tests: NULL-Fallback für fehlende Coins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_onchain_empty_data_returns_empty_df() -> None:
    """Adapter darf KEINEN Fehler werfen wenn API keine Daten zurückgibt (NULL-Fallback)."""
    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_EMPTY_RESPONSE))

        adapter = CoinMetricsAdapter()
        # Muss leeren DataFrame zurückgeben, KEINEN Fehler werfen
        df = await adapter.fetch_onchain(["UNKNOWN-COIN"], start="2024-01-01")

    assert df is not None
    assert len(df) == 0


@pytest.mark.asyncio
async def test_fetch_onchain_404_returns_empty_df() -> None:
    """Bei 404 (Coin nicht in Coin Metrics) muss adapter leeren DataFrame zurückgeben."""
    import httpx

    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_resp = _make_mock_response({}, status_code=404)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_resp,
        )
        mock_client.get = AsyncMock(return_value=mock_resp)

        adapter = CoinMetricsAdapter()
        # 404 = Coin nicht verfügbar → leerer DataFrame, kein Raise
        df = await adapter.fetch_onchain(["UNKNOWN"], start="2024-01-01")

    assert df is not None
    assert len(df) == 0


# ---------------------------------------------------------------------------
# Tests: Retry-Logik
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_onchain_retry_on_transient_error() -> None:
    """Adapter muss bei Netzwerkfehlern maximal _RETRIES=2 mal wiederholen."""
    import httpx

    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    call_count = 0

    async def side_effect(*args: Any, **kwargs: Any) -> None:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise httpx.ConnectError("Connection refused")
        return _make_mock_response(_SAMPLE_RESPONSE)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=side_effect)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            adapter = CoinMetricsAdapter()
            df = await adapter.fetch_onchain(["btc"], start="2024-01-01")

    assert call_count == 3  # 2 Fehler + 1 Erfolg (insgesamt 3 Versuche)
    assert len(df) > 0


@pytest.mark.asyncio
async def test_fetch_onchain_raises_after_all_retries_exhausted() -> None:
    """Nach _RETRIES+1 fehlgeschlagenen Versuchen muss eine Exception geraised werden."""
    import httpx

    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            adapter = CoinMetricsAdapter()
            with pytest.raises(httpx.ConnectError):
                await adapter.fetch_onchain(["btc"], start="2024-01-01")


@pytest.mark.asyncio
async def test_fetch_onchain_exponential_backoff() -> None:
    """Adapter muss Exponential Backoff verwenden: _BASE_DELAY * 2**attempt."""
    import httpx

    from backend.infrastructure.adapters.coin_metrics_adapter import CoinMetricsAdapter

    call_count = 0
    sleep_delays: list[float] = []

    async def side_effect(*args: Any, **kwargs: Any) -> None:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise httpx.ConnectError("Connection refused")
        return _make_mock_response(_SAMPLE_RESPONSE)

    async def mock_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=side_effect)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            adapter = CoinMetricsAdapter()
            await adapter.fetch_onchain(["btc"], start="2024-01-01")

    # Erster Retry: 1.0s, zweiter Retry: 2.0s
    assert len(sleep_delays) == 2
    assert abs(sleep_delays[0] - 1.0) < 1e-9  # _BASE_DELAY * 2**0
    assert abs(sleep_delays[1] - 2.0) < 1e-9  # _BASE_DELAY * 2**1
