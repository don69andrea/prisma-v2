"""Unit-Tests für FearGreedAdapter — httpx gemockt, kein Netzwerk-Call."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestFearGreedAdapterCaching:
    def test_fresh_call_fetches_from_api(self) -> None:
        """Erster Aufruf ohne Cache → HTTP-Request an alternative.me."""
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()
        mock_data = {
            "data": [{"value": "35", "value_classification": "Fear", "timestamp": "1700000000"}]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.json.return_value = mock_data
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            import asyncio

            result = asyncio.run(adapter.get_current())

        assert result["value"] == 35
        assert result["label"] == "Fear"
        assert "timestamp" in result

    def test_cached_result_returned_without_http_call(self) -> None:
        """Zweiter Aufruf innerhalb TTL → kein HTTP-Request."""
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()
        cached_data = {"value": 42, "label": "Fear", "timestamp": "1700000000"}
        adapter._cached = cached_data
        adapter._cached_at = datetime.now(tz=UTC)  # frisch gecacht

        with patch("httpx.AsyncClient") as mock_client_cls:
            import asyncio

            result = asyncio.run(adapter.get_current())
            mock_client_cls.assert_not_called()

        assert result["value"] == 42

    def test_stale_cache_triggers_new_request(self) -> None:
        """Cache älter als 3600 Sekunden → neuer HTTP-Request."""
        from datetime import timedelta

        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()
        adapter._cached = {"value": 99, "label": "Extreme Greed", "timestamp": "old"}
        adapter._cached_at = datetime.now(tz=UTC) - timedelta(seconds=3700)

        mock_data = {
            "data": [{"value": "20", "value_classification": "Extreme Fear", "timestamp": "new"}]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.json.return_value = mock_data
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            import asyncio

            result = asyncio.run(adapter.get_current())

        assert result["value"] == 20  # Neuer Wert, nicht der gecachte 99


class TestFearGreedAdapterFallback:
    def test_api_failure_returns_neutral_fallback(self) -> None:
        """HTTP-Fehler → Fallback-Wert 50/Neutral."""
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

            import asyncio

            result = asyncio.run(adapter.get_current())

        assert result["value"] == 50
        assert result["label"] == "Neutral"
        assert "timestamp" in result

    def test_api_failure_does_not_overwrite_valid_cache(self) -> None:
        """Frischer Cache bleibt bei API-Fehler erhalten."""
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()
        adapter._cached = {"value": 30, "label": "Fear", "timestamp": "cached"}
        adapter._cached_at = datetime.now(tz=UTC)  # frisch gecacht

        with patch("httpx.AsyncClient") as mock_client_cls:
            import asyncio

            result = asyncio.run(adapter.get_current())
            # Frischer Cache → kein HTTP-Call → kein Fallback
            mock_client_cls.assert_not_called()

        assert result["value"] == 30


class TestFearGreedAdapterResponseFormat:
    def test_value_is_integer(self) -> None:
        """'value' muss int sein, nicht String (API liefert Strings)."""
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()
        mock_data = {
            "data": [{"value": "73", "value_classification": "Greed", "timestamp": "1700000000"}]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.json.return_value = mock_data
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            import asyncio

            result = asyncio.run(adapter.get_current())

        assert isinstance(result["value"], int)
        assert result["value"] == 73

    def test_all_required_keys_present(self) -> None:
        """Antwort enthält 'value', 'label', 'timestamp'."""
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

        adapter = FearGreedAdapter()
        mock_data = {
            "data": [{"value": "55", "value_classification": "Neutral", "timestamp": "1700000000"}]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.json.return_value = mock_data
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            import asyncio

            result = asyncio.run(adapter.get_current())

        assert "value" in result
        assert "label" in result
        assert "timestamp" in result
