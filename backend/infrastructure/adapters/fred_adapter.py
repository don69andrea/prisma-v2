"""FRED (Federal Reserve Economic Data) Adapter — Schweizer CPI YoY-Rate.

Kein API-Key für CSV-Endpunkt erforderlich. Funktioniert von Render-IPs.
FRED API-Dokumentation: https://fred.stlouisfed.org/docs/api/fred/

Verwendete Serie:
  CHECPIALLMINMEI  — Schweizer CPI Gesamtindex (monthly, Index 2015=100)
  → YoY-Veränderung wird lokal aus den letzten 13 Monatswerten berechnet.

Hinweis: SNB-Leitzins kommt von snb_adapter.py (data.snb.ch).
         CHF/EUR kommt von ecb_fx_adapter.py (ECB SDW REST-API).
"""

from __future__ import annotations

import logging

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_FRED_CSV_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Schweizer CPI Index (OECD MEI, 2015=100) — nicht YoY; wird selbst berechnet
_CH_CPI_SERIES = "CHECPIALLMINMEI"

_FALLBACK_CH_CPI = 0.3   # realistisch für CH 2025/2026


async def _fetch_fred_csv_values(series_id: str, n: int = 14) -> list[float]:
    """Holt die letzten `n` gültigen Werte einer FRED-Datenserie als CSV.

    Gibt leere Liste zurück wenn der Call scheitert.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _FRED_CSV_BASE,
                params={"id": series_id},
                headers={"Accept": "text/csv"},
            )
            resp.raise_for_status()
            lines = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
            values: list[float] = []
            for line in lines[1:]:   # Zeile 0 = Header
                parts = line.split(",")
                if len(parts) >= 2 and parts[1].strip() not in (".", ""):
                    values.append(float(parts[1].strip()))
            return values[-n:] if values else []

    except Exception as exc:
        _logger.warning("FRED %s nicht abrufbar: %s", series_id, exc)
        return []


async def fetch_swiss_cpi_fred() -> float:
    """Schweizer CPI YoY-Veränderungsrate (%) berechnet aus FRED-Indexwerten.

    FRED liefert den CPI-Index (2015=100), kein YoY direkt.
    Berechnung: (Index_aktuell / Index_vor_12_Monaten - 1) × 100

    Verwendung: MacroContext.inflation_ch — Makro-Klima-Bestimmung.
    """
    values = await _fetch_fred_csv_values(_CH_CPI_SERIES, n=14)
    if len(values) >= 13:
        current = values[-1]
        year_ago = values[-13]
        if year_ago > 0:
            yoy = round((current / year_ago - 1) * 100, 2)
            if -5.0 <= yoy <= 15.0:   # Plausibilitäts-Check
                _logger.info("Schweizer CPI YoY (FRED): %.2f%%", yoy)
                return yoy

    _logger.warning("FRED CPI-Berechnung fehlgeschlagen — Fallback %.1f%%", _FALLBACK_CH_CPI)
    return _FALLBACK_CH_CPI
