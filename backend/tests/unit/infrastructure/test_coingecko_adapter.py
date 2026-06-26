"""Unit-Tests für CoinGeckoAdapter — CoinGeckoAPI gemockt, kein Netzwerk-Call."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch


def _make_market_entry(coin_id: str = "bitcoin", price: float = 50000.0) -> dict[str, object]:
    return {
        "id": coin_id,
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": price,
        "market_cap": 1_000_000_000_000,
        "market_cap_rank": 1,
        "price_change_percentage_24h": 1.5,
        "price_change_percentage_7d_in_currency": 5.2,
        "ath_change_percentage": -30.0,
        "total_volume": 5_000_000_000,
    }


class TestCoinGeckoAdapterCache:
    def test_first_call_fetches_from_api(self) -> None:
        """Erster Aufruf ohne Cache → API-Call via to_thread."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        mock_result = [_make_market_entry()]

        with patch.object(adapter._cg, "get_coins_markets", return_value=mock_result):
            result = asyncio.run(adapter.get_market_data(["bitcoin"]))

        assert len(result) == 1
        assert result[0]["id"] == "bitcoin"

    def test_second_call_uses_cache(self) -> None:
        """Zweiter Aufruf innerhalb TTL → kein API-Call."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        adapter._market_cache = [_make_market_entry("bitcoin", 50000.0)]
        adapter._market_cached_at = datetime.now(tz=UTC)

        with patch.object(adapter._cg, "get_coins_markets") as mock_cg:
            result = asyncio.run(adapter.get_market_data(["bitcoin"]))
            mock_cg.assert_not_called()

        assert result[0]["current_price"] == 50000.0

    def test_stale_cache_triggers_new_api_call(self) -> None:
        """Cache älter als 600 Sekunden → neuer API-Call."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        adapter._market_cache = [_make_market_entry("bitcoin", 1.0)]
        adapter._market_cached_at = datetime.now(tz=UTC) - timedelta(seconds=700)

        new_data = [_make_market_entry("bitcoin", 60000.0)]
        with patch.object(adapter._cg, "get_coins_markets", return_value=new_data):
            result = asyncio.run(adapter.get_market_data(["bitcoin"]))

        assert result[0]["current_price"] == 60000.0

    def test_cache_updated_after_successful_call(self) -> None:
        """Nach erfolgreichem API-Call ist der Cache befüllt."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        assert adapter._market_cache is None

        mock_data = [_make_market_entry()]
        with patch.object(adapter._cg, "get_coins_markets", return_value=mock_data):
            asyncio.run(adapter.get_market_data(["bitcoin"]))

        assert adapter._market_cache is not None
        assert adapter._market_cached_at is not None


class TestCoinGeckoAdapterFallback:
    def test_api_failure_returns_empty_list_when_no_cache(self) -> None:
        """Fehler ohne Cache → leere Liste (kein Absturz)."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()

        with patch.object(adapter._cg, "get_coins_markets", side_effect=Exception("Rate limit")):
            result = asyncio.run(adapter.get_market_data(["bitcoin"]))

        assert result == []

    def test_api_failure_returns_stale_cache(self) -> None:
        """Fehler mit veralteter Cache → veralteter Cache als Fallback."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        stale_data = [_make_market_entry("bitcoin", 45000.0)]
        adapter._market_cache = stale_data
        adapter._market_cached_at = datetime.now(tz=UTC) - timedelta(seconds=700)

        with patch.object(adapter._cg, "get_coins_markets", side_effect=Exception("Timeout")):
            result = asyncio.run(adapter.get_market_data(["bitcoin"]))

        assert result == stale_data
        assert result[0]["current_price"] == 45000.0


class TestCoinGeckoAdapterBatchCall:
    def test_multiple_coins_fetched_in_single_call(self) -> None:
        """10 Coins werden in einem einzigen API-Call abgefragt."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        coin_ids = ["bitcoin", "ethereum", "solana"]
        mock_data = [_make_market_entry(cid) for cid in coin_ids]

        call_count = 0

        def mock_get_markets(**kwargs):
            nonlocal call_count
            call_count += 1
            return mock_data

        with patch.object(adapter._cg, "get_coins_markets", side_effect=mock_get_markets):
            asyncio.run(adapter.get_market_data(coin_ids))

        assert call_count == 1  # Nur ein einziger API-Call

    def test_returns_list_type(self) -> None:
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()
        mock_data = [_make_market_entry()]

        with patch.object(adapter._cg, "get_coins_markets", return_value=mock_data):
            result = asyncio.run(adapter.get_market_data(["bitcoin"]))

        assert isinstance(result, list)

    def test_empty_coins_list_still_works(self) -> None:
        """Leere Coin-Liste → leere Antwort (kein Crash)."""
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter

        adapter = CoinGeckoAdapter()

        with patch.object(adapter._cg, "get_coins_markets", return_value=[]):
            result = asyncio.run(adapter.get_market_data([]))

        assert result == []
