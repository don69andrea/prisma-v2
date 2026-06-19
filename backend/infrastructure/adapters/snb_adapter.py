"""SNB Data Adapter — Leitzins von SNB data.snb.ch (mit Fallback auf hardcodierte Historie)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

import httpx

_logger = logging.getLogger(__name__)

_SNB_CSV_URL = "https://data.snb.ch/api/cube/rendsnb/data/csv/de?dimSel=D0(SR)"
_TIMEOUT = 5.0

# Hardcodierte SNB-Leitzins-Historie (Fallback) — SR = Sichteinlagenzins SNB
_SNB_RATE_HISTORY: list[tuple[date, float]] = [
    (date(2022, 6, 16), -0.25),
    (date(2022, 9, 22), 0.50),
    (date(2022, 12, 15), 1.00),
    (date(2023, 3, 23), 1.50),
    (date(2023, 6, 22), 1.75),
    (date(2024, 3, 21), 1.50),
    (date(2024, 6, 20), 1.25),
    (date(2024, 9, 26), 1.00),
    (date(2024, 12, 12), 0.50),
    (date(2025, 3, 20), 0.25),
    (date(2025, 6, 19), 0.0),
]


def _snb_rate_from_history(target: date) -> float:
    eligible = [(d, r) for d, r in sorted(_SNB_RATE_HISTORY) if d <= target]
    return eligible[-1][1] if eligible else -0.75


async def fetch_current_snb_rate() -> float:
    """Holt den aktuellen SNB-Leitzins von data.snb.ch.

    Fällt bei Netzwerkfehlern auf die hardcodierte Historie zurück.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_SNB_CSV_URL)
            resp.raise_for_status()
            lines = resp.text.splitlines()
            # CSV-Format: Datum;Wert (letzte Zeile = neuester Eintrag)
            data_lines = [
                line for line in lines if line and not line.startswith(('"', "Date", ";"))
            ]
            if data_lines:
                last = data_lines[-1]
                parts = last.replace('"', "").split(";")
                if len(parts) >= 2 and parts[-1].strip():
                    return float(parts[-1].strip().replace(",", "."))
    except Exception:
        _logger.warning("SNB API nicht erreichbar — nutze Fallback-Historie", exc_info=True)

    return _snb_rate_from_history(datetime.now(tz=UTC).date())
