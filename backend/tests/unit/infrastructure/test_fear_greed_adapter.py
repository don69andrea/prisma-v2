"""Unit Tests für FearGreedAdapter — httpx wird vollständig gemockt.

Test-First (TDD / RED-Phase):
- Datum-Parsing aus Unix-Timestamp (String → datetime.date via UTC)
- Wert-Extraktion: value als int, value_classification als str
- Vollständige History wenn limit=0
- Retry-Logik: max 2 Retries, Exponential Backoff
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_SAMPLE_RESPONSE = {
    "name": "Fear and Greed Index",
    "data": [
        {
            "value": "25",
            "value_classification": "Extreme Fear",
            "timestamp": "1704067200",  # 2024-01-01 00:00:00 UTC
            "time_until_update": "3600",
        },
        {
            "value": "30",
            "value_classification": "Fear",
            "timestamp": "1703980800",  # 2023-12-31 00:00:00 UTC
            "time_until_update": "3600",
        },
        {
            "value": "72",
            "value_classification": "Greed",
            "timestamp": "1703894400",  # 2023-12-30 00:00:00 UTC
            "time_until_update": "3600",
        },
    ],
    "metadata": {"error": None},
}

_SINGLE_RESPONSE = {
    "data": [
        {
            "value": "50",
            "value_classification": "Neutral",
            "timestamp": "1704067200",
            "time_until_update": "3600",
        }
    ]
}


def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Erstellt einen Mock für eine httpx-Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: URL + limit=0 (vollständige History)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_history_uses_limit_zero() -> None:
    """Adapter muss limit=0 verwenden um vollständige History zu laden."""
    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = FearGreedAdapter()
        await adapter.fetch_history()

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        assert "alternative.me" in url or "api.alternative.me" in url
        assert "fng" in url


@pytest.mark.asyncio
async def test_fetch_history_url_contains_limit_zero() -> None:
    """URL-Parameter müssen limit=0 und format=json enthalten."""
    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = FearGreedAdapter()
        await adapter.fetch_history()

        call_args = mock_client.get.call_args
        # Check either URL params or kwargs params
        url = call_args[0][0] if call_args[0] else ""
        kwargs_params = call_args.kwargs.get("params", {})

        # limit=0 entweder in URL oder params
        has_limit_zero = "limit=0" in url or str(kwargs_params.get("limit", "")) == "0"
        assert has_limit_zero, f"limit=0 fehlt. URL: {url}, params: {kwargs_params}"


# ---------------------------------------------------------------------------
# Tests: Datum-Parsing aus Unix-Timestamp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_history_parses_unix_timestamp_to_date() -> None:
    """Adapter muss Unix-Timestamp-String korrekt zu datetime.date parsen (UTC)."""
    from datetime import date

    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = FearGreedAdapter()
        df = await adapter.fetch_history()

    assert "date" in df.columns
    # timestamp "1704067200" = 2024-01-01 UTC
    assert df.iloc[0]["date"] == date(2024, 1, 1)
    # timestamp "1703980800" = 2023-12-31 UTC
    assert df.iloc[1]["date"] == date(2023, 12, 31)
    # timestamp "1703894400" = 2023-12-30 UTC
    assert df.iloc[2]["date"] == date(2023, 12, 30)


# ---------------------------------------------------------------------------
# Tests: Wert-Extraktion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_history_extracts_value_as_int() -> None:
    """Der 'fear_greed'-Wert muss als Integer extrahiert werden."""
    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = FearGreedAdapter()
        df = await adapter.fetch_history()

    assert "fear_greed" in df.columns
    assert df.iloc[0]["fear_greed"] == 25
    assert isinstance(df.iloc[0]["fear_greed"], int | float)  # numpy int auch ok


@pytest.mark.asyncio
async def test_fetch_history_extracts_classification_as_str() -> None:
    """Die 'fg_classification' muss als String extrahiert werden."""
    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = FearGreedAdapter()
        df = await adapter.fetch_history()

    assert "fg_classification" in df.columns
    assert df.iloc[0]["fg_classification"] == "Extreme Fear"
    assert df.iloc[1]["fg_classification"] == "Fear"
    assert df.iloc[2]["fg_classification"] == "Greed"


@pytest.mark.asyncio
async def test_fetch_history_returns_all_entries() -> None:
    """Alle Einträge der Response müssen im DataFrame vorhanden sein."""
    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SAMPLE_RESPONSE))

        adapter = FearGreedAdapter()
        df = await adapter.fetch_history()

    assert len(df) == 3  # 3 Einträge im Sample


# ---------------------------------------------------------------------------
# Tests: Retry-Logik
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_history_retry_on_transient_error() -> None:
    """Adapter muss bei Netzwerkfehlern maximal _RETRIES=2 mal wiederholen."""
    import httpx

    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    call_count = 0

    async def side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
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
            adapter = FearGreedAdapter()
            df = await adapter.fetch_history()

    assert call_count == 3  # 2 Fehler + 1 Erfolg
    assert len(df) > 0


@pytest.mark.asyncio
async def test_fetch_history_raises_after_all_retries_exhausted() -> None:
    """Nach _RETRIES+1 Versuchen muss Exception geraised werden."""
    import httpx

    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            adapter = FearGreedAdapter()
            with pytest.raises(httpx.ConnectError):
                await adapter.fetch_history()


@pytest.mark.asyncio
async def test_fetch_history_exponential_backoff() -> None:
    """Adapter muss Exponential Backoff verwenden: _BASE_DELAY * 2**attempt."""
    import httpx

    from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

    call_count = 0
    sleep_delays: list[float] = []

    async def side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
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
            adapter = FearGreedAdapter()
            await adapter.fetch_history()

    assert len(sleep_delays) == 2
    assert abs(sleep_delays[0] - 1.0) < 1e-9  # _BASE_DELAY * 2**0
    assert abs(sleep_delays[1] - 2.0) < 1e-9  # _BASE_DELAY * 2**1
