"""FearGreedAdapter — Fear & Greed Index via alternative.me API.

Alle HTTP-Aufrufe via httpx.AsyncClient.
Retry: _RETRIES=2, _BASE_DELAY=1.0, Exponential Backoff (base * 2**attempt).
Endpoint: https://api.alternative.me/fng/?limit=0&format=json

Unix-Timestamp-Parsing: datetime.fromtimestamp(int(ts), tz=UTC).date()
DataFrame-Spalten: [date, fear_greed, fg_classification]
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd

_logger = logging.getLogger(__name__)

_BASE_URL = "https://api.alternative.me/fng/"
_RETRIES = 2
_BASE_DELAY = 1.0
_CACHE_TTL_SECONDS = 3600

_COLUMNS = ["date", "fear_greed", "fg_classification"]


def _validate_fear_greed(value: int) -> int | None:
    """Gibt None zurück wenn der Fear&Greed-Wert ausserhalb 0–100 liegt."""
    if not (0 <= value <= 100):
        return None
    return value


class FearGreedAdapter:
    """Adapter für den Fear & Greed Index via alternative.me API.

    fetch_history(): vollständige History als DataFrame [date, fear_greed, fg_classification]
    get_current(): aktueller Wert als Dict {value, label, timestamp}, gecacht 1h
    """

    def __init__(self) -> None:
        self._cached: dict[str, Any] | None = None
        self._cached_at: datetime | None = None

    async def fetch_history(self) -> pd.DataFrame:
        """Lädt die vollständige Fear & Greed Index History.

        Returns:
            DataFrame mit Spalten: date (datetime.date), fear_greed (int),
            fg_classification (str).

        Raises:
            httpx.ConnectError / httpx.TimeoutException: Nach _RETRIES+1 fehlgeschlagenen
            Versuchen bei Netzwerkfehlern.
        """
        params = {
            "limit": "0",
            "format": "json",
        }

        last_exc: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(_BASE_URL, params=params)
                    response.raise_for_status()

                    data = response.json().get("data", [])
                    return self._transform(data)

            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "Fear&Greed request attempt %d/%d failed: %s — retry in %.1fs",
                        attempt + 1,
                        _RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    async def get_current(self) -> dict[str, Any]:
        """Gibt {"value": int, "label": str, "timestamp": str} zurück.

        Cacht das Ergebnis 1 Stunde (Index wird täglich aktualisiert).
        Fallback auf Wert 50 (Neutral) wenn API nicht erreichbar.
        """
        now = datetime.now(tz=UTC)
        if self._cached_at and (now - self._cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return self._cached  # type: ignore[return-value]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_BASE_URL, params={"limit": "1", "format": "json"})
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

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        """Konvertiert Unix-Timestamp-String zu UTC-aware datetime."""
        return datetime.fromtimestamp(int(ts), tz=UTC)

    @classmethod
    def _transform(cls, data: list[dict[str, str]]) -> pd.DataFrame:
        """Transformiert alternative.me JSON-Data in internes DataFrame-Format."""
        rows = []
        for entry in data:
            dt = cls._parse_timestamp(entry["timestamp"])
            rows.append(
                {
                    "date": dt.date(),
                    "fear_greed": int(entry["value"]),
                    "fg_classification": str(entry["value_classification"]),
                }
            )

        return pd.DataFrame(rows, columns=_COLUMNS)
