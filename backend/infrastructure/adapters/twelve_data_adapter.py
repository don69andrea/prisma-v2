"""Twelve Data Adapter — Zuverlässige Live-Kursdaten für Schweizer Aktien.

Twelve Data funktioniert von Render-IPs (kein Block wie bei yfinance).
Kostenloser Plan: 800 API-Calls/Tag, 8 Calls/Minute.

API-Dokumentation: https://twelvedata.com/docs
API-Key: https://twelvedata.com/register (kostenlos)
Render env var: TWELVE_DATA_API_KEY

Unterstützte Börsen für SMI-Titel:
  - SIX Swiss Exchange: NESN:SIX, NOVN:SIX, ROG:SIX etc.
  - Falls SIX nicht verfügbar: Fallback auf OTC/Frankfurt
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

_logger = logging.getLogger(__name__)

_BASE_URL = "https://api.twelvedata.com"
_TIMEOUT = 10.0

# SIX Exchange Symbol-Mapping: interner Ticker → Twelve Data Symbol
_TICKER_TO_TD: dict[str, str] = {
    "NESN": "NESN:SIX",
    "NOVN": "NOVN:SIX",
    "ROG": "ROG:SIX",
    "ABBN": "ABBN:SIX",
    "ZURN": "ZURN:SIX",
    "UBSG": "UBSG:SIX",
    "UHR": "UHR:SIX",
    "GEBN": "GEBN:SIX",
    "GIVN": "GIVN:SIX",
    "LONN": "LONN:SIX",
    "SREN": "SREN:SIX",
    "SGKN": "SGKN:SIX",
    "SLHN": "SLHN:SIX",
    "SCMN": "SCMN:SIX",
    "SIKA": "SIKA:SIX",
    "HOLN": "HOLN:SIX",
    "PGHN": "PGHN:SIX",
    "KNIN": "KNIN:SIX",
    "CFR": "CFR:SIX",
    "STMN": "STMN:SIX",
    # Krypto (als Bonus — kein Key nötig für Krypto-Preise)
    "BTC": "BTC/CHF:Coinbase",
    "ETH": "ETH/CHF:Coinbase",
}


def _get_api_key() -> str | None:
    return os.getenv("TWELVE_DATA_API_KEY")


class TwelveDataAdapter:
    """Adapter für Twelve Data API — Live-Kurse und technische Indikatoren.

    Fällt graceful zurück wenn kein API-Key gesetzt ist (gibt None zurück).
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or _get_api_key()
        self._available = self._api_key is not None
        if not self._available:
            _logger.info("TWELVE_DATA_API_KEY nicht gesetzt — Twelve Data Adapter deaktiviert")

    @property
    def available(self) -> bool:
        return self._available

    async def get_quote(self, ticker: str) -> dict[str, Any] | None:
        """Aktueller Kurs + Tagesveränderung für einen Ticker.

        Returns:
            {
                "ticker": "NESN",
                "price": 105.80,
                "change": 1.20,
                "change_pct": 1.15,
                "volume": 1234567,
                "exchange": "SIX",
                "currency": "CHF",
                "close_yesterday": 104.60,
            }
        """
        if not self._available:
            return None

        symbol = _TICKER_TO_TD.get(ticker.upper(), f"{ticker.upper()}:SIX")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/quote",
                    params={"symbol": symbol, "apikey": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") == "error":
                    _logger.warning("Twelve Data Fehler für %s: %s", ticker, data.get("message"))
                    return None

                return {
                    "ticker": ticker.upper(),
                    "price": float(data.get("close", 0)),
                    "change": float(data.get("change", 0)),
                    "change_pct": float(data.get("percent_change", 0)),
                    "volume": int(data.get("volume", 0) or 0),
                    "exchange": data.get("exchange", "SIX"),
                    "currency": data.get("currency", "CHF"),
                    "close_yesterday": float(data.get("previous_close", 0)),
                }
        except Exception as exc:
            _logger.warning("Twelve Data Quote für %s fehlgeschlagen: %s", ticker, exc)
            return None

    async def get_time_series(
        self,
        ticker: str,
        interval: str = "1day",
        outputsize: int = 30,
    ) -> list[dict[str, Any]]:
        """Historische OHLCV-Daten für einen Ticker.

        Args:
            ticker:     Interner Ticker (z.B. "NESN")
            interval:   "1min", "5min", "1h", "1day", "1week"
            outputsize: Anzahl Datenpunkte (max 5000 im kostenlosen Plan)

        Returns:
            Liste von {"datetime", "open", "high", "low", "close", "volume"}
        """
        if not self._available:
            return []

        symbol = _TICKER_TO_TD.get(ticker.upper(), f"{ticker.upper()}:SIX")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/time_series",
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "outputsize": outputsize,
                        "apikey": self._api_key,
                        "format": "JSON",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") == "error":
                    _logger.warning(
                        "Twelve Data Time Series Fehler für %s: %s",
                        ticker,
                        data.get("message"),
                    )
                    return []

                values = data.get("values", [])
                return [
                    {
                        "datetime": v["datetime"],
                        "open": float(v["open"]),
                        "high": float(v["high"]),
                        "low": float(v["low"]),
                        "close": float(v["close"]),
                        "volume": int(v.get("volume", 0) or 0),
                    }
                    for v in values
                ]
        except Exception as exc:
            _logger.warning("Twelve Data Time Series für %s fehlgeschlagen: %s", ticker, exc)
            return []

    async def get_rsi(self, ticker: str, period: int = 14) -> float | None:
        """RSI (Relative Strength Index) direkt von Twelve Data berechnen lassen.

        Twelve Data berechnet technische Indikatoren server-seitig —
        kein lokales pandas/ta nötig.
        """
        if not self._available:
            return None

        symbol = _TICKER_TO_TD.get(ticker.upper(), f"{ticker.upper()}:SIX")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/rsi",
                    params={
                        "symbol": symbol,
                        "interval": "1day",
                        "time_period": period,
                        "outputsize": 1,
                        "apikey": self._api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") == "error":
                    return None
                values = data.get("values", [])
                return float(values[0]["rsi"]) if values else None
        except Exception:
            return None

    async def get_batch_quotes(self, tickers: list[str]) -> dict[str, dict[str, Any]]:
        """Mehrere Kurse in einem einzigen API-Call (spart Rate-Limit).

        Twelve Data erlaubt bis zu 120 Symbole pro Batch-Anfrage.
        """
        if not self._available or not tickers:
            return {}

        symbols = ",".join(_TICKER_TO_TD.get(t.upper(), f"{t.upper()}:SIX") for t in tickers[:120])
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/quote",
                    params={"symbol": symbols, "apikey": self._api_key},
                )
                resp.raise_for_status()
                raw = resp.json()

            result: dict[str, dict[str, Any]] = {}
            # Batch-Response: entweder direkt ein Dict (1 Symbol) oder Dict of Dicts
            if "symbol" in raw:
                raw = {raw["symbol"]: raw}

            for symbol, data in raw.items():
                if data.get("status") == "error":
                    continue
                # Ticker aus Symbol extrahieren (z.B. "NESN:SIX" → "NESN")
                ticker = symbol.split(":")[0]
                result[ticker] = {
                    "ticker": ticker,
                    "price": float(data.get("close", 0)),
                    "change": float(data.get("change", 0)),
                    "change_pct": float(data.get("percent_change", 0)),
                    "volume": int(data.get("volume", 0) or 0),
                    "currency": data.get("currency", "CHF"),
                    "close_yesterday": float(data.get("previous_close", 0)),
                }
            _logger.info(
                "Twelve Data Batch: %d/%d Kurse erhalten",
                len(result),
                len(tickers),
            )
            return result

        except Exception as exc:
            _logger.warning("Twelve Data Batch fehlgeschlagen: %s", exc)
            return {}
