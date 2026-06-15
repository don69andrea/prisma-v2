"""CoinGecko API-Adapter für Marktdaten in CHF (Free Tier, kein API-Key nötig)."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from pycoingecko import CoinGeckoAPI

_logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 600


class CoinGeckoAdapter:
    """Wrapper um die CoinGecko API mit 10-Minuten-Cache.

    Ein einziger Batch-Call für alle 10 Coins schont das Free-Tier-Limit.
    """

    def __init__(self, api_key: str = "") -> None:
        self._cg = CoinGeckoAPI(api_key=api_key)
        self._market_cache: list[dict] | None = None
        self._market_cached_at: datetime | None = None

    async def get_market_data(
        self, coin_ids: list[str], vs_currency: str = "chf"
    ) -> list[dict]:
        """Markt-Daten für mehrere Coins in einem API-Call (Batch)."""
        now = datetime.now(tz=UTC)
        if (
            self._market_cached_at
            and (now - self._market_cached_at).total_seconds() < _CACHE_TTL_SECONDS
            and self._market_cache is not None
        ):
            return self._market_cache

        try:
            result: list[dict] = await asyncio.to_thread(
                self._cg.get_coins_markets,
                vs_currency=vs_currency,
                ids=",".join(coin_ids),
                order="market_cap_desc",
                per_page=50,
                page=1,
                sparkline=False,
                price_change_percentage="24h,7d",
            )
            self._market_cache = result
            self._market_cached_at = now
            return result
        except Exception:
            _logger.warning("CoinGeckoAdapter: API-Call fehlgeschlagen")
            return self._market_cache or []
