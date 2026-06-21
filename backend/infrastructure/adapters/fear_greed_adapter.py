"""FearGreedAdapter — Fear & Greed Index History via alternative.me API.

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

import httpx
import pandas as pd

_logger = logging.getLogger(__name__)

_BASE_URL = "https://api.alternative.me/fng/"
_RETRIES = 2
_BASE_DELAY = 1.0

_COLUMNS = ["date", "fear_greed", "fg_classification"]


class FearGreedAdapter:
    """Adapter für den Fear & Greed Index via alternative.me API.

    Liefert die vollständige History als DataFrame mit Spalten:
    [date, fear_greed, fg_classification]
    """

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

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        """Konvertiert Unix-Timestamp-String zu UTC-aware datetime."""
        return datetime.fromtimestamp(int(ts), tz=UTC)

    @classmethod
    def _transform(cls, data: list[dict[str, str]]) -> pd.DataFrame:
        """Transformiert alternative.me JSON-Data in internes DataFrame-Format.

        Args:
            data: Liste von Dicts aus response["data"]

        Returns:
            DataFrame mit Spalten: date, fear_greed, fg_classification
        """
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
