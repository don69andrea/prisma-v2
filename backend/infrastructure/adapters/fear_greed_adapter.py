"""Fear & Greed Index-Adapter via alternative.me (kostenlos, kein API-Key)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

_logger = logging.getLogger(__name__)

_URL = "https://api.alternative.me/fng/?limit=1&format=json"
_CACHE_TTL_SECONDS = 3600


def _validate_fear_greed(value: int) -> int | None:
    """Gibt None zurück wenn der Fear&Greed-Wert ausserhalb 0–100 liegt."""
    if not (0 <= value <= 100):
        return None
    return value


class FearGreedAdapter:
    """Ruft den Crypto Fear & Greed Index von alternative.me ab.

    Cacht das Ergebnis 1 Stunde (Index wird täglich aktualisiert).
    Fallback auf Wert 50 (Neutral) wenn API nicht erreichbar.
    """

    def __init__(self) -> None:
        self._cached: dict[str, Any] | None = None
        self._cached_at: datetime | None = None

    async def get_current(self) -> dict[str, Any]:
        """Gibt {"value": int, "label": str, "timestamp": str} zurück."""
        now = datetime.now(tz=UTC)
        if self._cached_at and (now - self._cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return self._cached  # type: ignore[return-value]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_URL)
                resp.raise_for_status()
                data = resp.json()["data"][0]
                value = int(data["value"])
                validated_value = _validate_fear_greed(value)
                if validated_value is None:
                    _logger.warning(
                        "FearGreedAdapter: Ungültiger Fear&Greed-Wert %d — Fallback auf 50",
                        value,
                    )
                    validated_value = 50
                result: dict[str, Any] = {
                    "value": validated_value,
                    "label": data["value_classification"],
                    "timestamp": data["timestamp"],
                }
                self._cached = result
                self._cached_at = now
                return result
        except Exception:
            _logger.warning("FearGreedAdapter: API nicht erreichbar — Fallback 50/Neutral")
            return {"value": 50, "label": "Neutral", "timestamp": now.isoformat()}
