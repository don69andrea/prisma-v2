"""ECB Foreign Exchange Adapter — CHF/EUR und andere Kurse via ECB Statistical Data Warehouse.

Kein API-Key erforderlich. Funktioniert zuverlässig von Render-IPs (im Gegensatz zu yfinance).
ECB SDW REST-API: https://sdw-wsrest.ecb.europa.eu/help/
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = 8.0
_ECB_BASE = "https://sdw-wsrest.ecb.europa.eu/service/data"

# ECB Series-Keys für relevante Kurse (CHF pro 1 EUR = EXR/D.CHF.EUR.SP00.A invertiert)
_EUR_CHF_KEY = "EXR/D.CHF.EUR.SP00.A"  # CHF per EUR (direkt, nicht invertiert)
_USD_CHF_KEY = "EXR/D.CHF.USD.SP00.A"  # CHF per USD
_GBP_CHF_KEY = "EXR/D.CHF.GBP.SP00.A"  # CHF per GBP

_FALLBACK_CHF_EUR = 0.93  # ca. CHF 0.93 per EUR (Stand 2025/2026)
_FALLBACK_CHF_USD = 0.89  # ca. CHF 0.89 per USD
_FALLBACK_CHF_GBP = 1.13  # ca. CHF 1.13 per GBP


async def _fetch_ecb_rate(series_key: str, fallback: float) -> float:
    """Holt einen Wechselkurs von der ECB SDW REST-API.

    Format: letzter Handelstag, Closing-Kurs (CHF per Fremdwährung).
    Gibt `fallback` zurück wenn der Call scheitert.
    """
    url = f"{_ECB_BASE}/{series_key}"
    params = {
        "format": "jsondata",
        "lastNObservations": "5",  # letzte 5 Handelstage als Puffer
        "detail": "dataonly",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            # ECB JSON-Format: data["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]
            # Observations sind nach Index sortiert, letzter = aktuellster
            datasets = data.get("dataSets", [])
            if not datasets:
                raise ValueError("Keine dataSets")
            series = datasets[0].get("series", {})
            if not series:
                raise ValueError("Keine series")

            first_series = next(iter(series.values()))
            obs = first_series.get("observations", {})
            if not obs:
                raise ValueError("Keine observations")

            # Neuester Wert
            latest_idx = str(max(int(k) for k in obs))
            value = obs[latest_idx][0]
            if value is None:
                raise ValueError("Letzter Kurs ist None")

            rate = round(float(value), 6)
            _logger.debug("ECB %s: %.6f", series_key, rate)
            return rate

    except Exception as exc:
        _logger.warning(
            "ECB FX-Abruf für %s fehlgeschlagen (%s) — Fallback %.4f",
            series_key,
            exc,
            fallback,
        )
        return fallback


async def fetch_chf_eur() -> float:
    """Aktueller CHF/EUR-Kurs (CHF pro 1 EUR) von der ECB.

    Beispiel: 0.9341 bedeutet 1 EUR = CHF 0.9341.
    Kein API-Key, kein Rate-Limit, funktioniert von Render-IPs.
    """
    return await _fetch_ecb_rate(_EUR_CHF_KEY, _FALLBACK_CHF_EUR)


async def fetch_chf_usd() -> float:
    """Aktueller CHF/USD-Kurs (CHF pro 1 USD) von der ECB."""
    return await _fetch_ecb_rate(_USD_CHF_KEY, _FALLBACK_CHF_USD)


async def fetch_chf_gbp() -> float:
    """Aktueller CHF/GBP-Kurs (CHF pro 1 GBP) von der ECB."""
    return await _fetch_ecb_rate(_GBP_CHF_KEY, _FALLBACK_CHF_GBP)


async def fetch_all_chf_rates() -> dict[str, float]:
    """Holt CHF/EUR, CHF/USD und CHF/GBP parallel von der ECB.

    Returns:
        {"chf_eur": 0.93, "chf_usd": 0.89, "chf_gbp": 1.13}
    """
    import asyncio

    eur, usd, gbp = await asyncio.gather(
        fetch_chf_eur(),
        fetch_chf_usd(),
        fetch_chf_gbp(),
    )
    fetched_at = datetime.now(UTC).isoformat()
    _logger.info(
        "ECB FX Rates (%s): CHF/EUR=%.4f CHF/USD=%.4f CHF/GBP=%.4f",
        fetched_at,
        eur,
        usd,
        gbp,
    )
    return {"chf_eur": eur, "chf_usd": usd, "chf_gbp": gbp}
