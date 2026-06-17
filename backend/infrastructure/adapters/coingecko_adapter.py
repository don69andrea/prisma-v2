"""CoinGecko API-Adapter für Marktdaten in CHF (Free Tier, kein API-Key nötig)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from pycoingecko import CoinGeckoAPI

_logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 600


def _validate_market_entry(entry: dict) -> bool:
    """Gibt False zurück wenn ein Marktdaten-Eintrag offensichtlich korrupt ist."""
    price = entry.get("current_price")
    return price is not None and price > 0


class CoinGeckoAdapter:
    """Wrapper um die CoinGecko API mit 10-Minuten-Cache.

    Ein einziger Batch-Call für alle 10 Coins schont das Free-Tier-Limit.
    """

    def __init__(self, api_key: str = "") -> None:
        self._cg = CoinGeckoAPI(api_key=api_key)
        self._market_cache: list[dict[str, Any]] | None = None
        self._market_cached_at: datetime | None = None

    async def get_market_data(
        self, coin_ids: list[str], vs_currency: str = "chf"
    ) -> list[dict[str, Any]]:
        """Markt-Daten für mehrere Coins in einem API-Call (Batch)."""
        now = datetime.now(tz=UTC)
        if (
            self._market_cached_at
            and (now - self._market_cached_at).total_seconds() < _CACHE_TTL_SECONDS
            and self._market_cache is not None
        ):
            return self._market_cache

        try:
            raw: list[dict[str, Any]] = await asyncio.to_thread(
                self._cg.get_coins_markets,
                vs_currency=vs_currency,
                ids=",".join(coin_ids),
                order="market_cap_desc",
                per_page=50,
                page=1,
                sparkline=False,
                price_change_percentage="24h,7d",
            )
            result = [e for e in raw if _validate_market_entry(e)]
            invalid = len(raw) - len(result)
            if invalid:
                _logger.warning("CoinGecko: %d ungültige Einträge gefiltert", invalid)
            self._market_cache = result
            self._market_cached_at = now
            return result
        except Exception:
            _logger.warning("CoinGeckoAdapter: API-Call fehlgeschlagen")
            return self._market_cache or []
