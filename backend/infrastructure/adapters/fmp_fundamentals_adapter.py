"""FMP (Financial Modeling Prep) Fundamentals Adapter — Phase 0 Coverage Probe.

Nutzt den bereits in config.py enthaltenen `fmp_api_key`.
Free Tier: 250 Calls/Tag, kein Rate-Limit-Enforcement nötig für den Probe (3 Titel).

Endpoint: GET https://financialmodelingprep.com/api/v3/key-metrics/{symbol}
  ?period=quarter&limit=40&apikey={key}
  Swiss-Ticker: NESN.SW (identisches Format wie yfinance)
  Liefert: pe (P/E), pb (P/B), roe, debtToEquity, freeCashFlowMargin, eps,
           dividendYield, marketCap — alles quartalsweise.
  PIT-Datum: `date` im Response ist das Quartalsende (period_end);
             `fillingDate` ist das Filing-Datum (publish_date, PIT-korrekt).

Leerer Key => Adapter deaktiviert (kein HTTP-Call, kein Boot-Fehler).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

log = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"


class FmpFundamentalsAdapter:
    def __init__(self, api_key: str) -> None:
        self._key = api_key
        self.enabled = bool(api_key) and api_key not in ("your-fmp-key", "change-me", "")

    @staticmethod
    def to_symbol(ticker: str) -> str:
        """NESN -> NESN.SW. Schon-suffixierte Ticker bleiben."""
        if "." in ticker:
            return ticker
        return f"{ticker}.SW"

    async def fetch_quarterly(self, ticker: str) -> list[dict[str, Any]]:
        """Liefert PIT-korrekte Quartals-Fundamentals als Dicts,
        bereit für stock_fundamentals (Schema 0032). Leere Liste wenn
        deaktiviert oder keine Coverage."""
        if not self.enabled:
            log.info("FMP deaktiviert (kein Key) — leere Coverage für %s", ticker)
            return []

        symbol = self.to_symbol(ticker)
        url = f"{_BASE}/key-metrics/{symbol}"
        params: dict[str, str | int] = {"period": "quarter", "limit": 40, "apikey": self._key}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)

        if resp.status_code != 200:
            log.warning("FMP %s -> HTTP %s (keine Coverage?)", symbol, resp.status_code)
            return []

        data = resp.json()
        if not isinstance(data, list) or not data:
            log.info("FMP %s: leere Antwort", symbol)
            return []

        rows: list[dict[str, Any]] = []
        for item in data:
            period_end_str = item.get("date")
            filling_date_str = item.get("fillingDate") or period_end_str
            if not period_end_str:
                continue
            try:
                period_end = date.fromisoformat(period_end_str)
                publish_date = date.fromisoformat(filling_date_str) if filling_date_str else None
            except ValueError:
                continue

            rows.append(
                {
                    "ticker": ticker,
                    "period_end": period_end,
                    "publish_date": publish_date,
                    "period_type": "quarterly",
                    "pe_ratio": _f(item, "pe"),
                    "pb_ratio": _f(item, "pb"),
                    "ev_ebitda": _f(item, "evToEbitda") or _f(item, "enterpriseValueOverEBITDA"),
                    "roe": _f_pct(item, "roe"),
                    "debt_equity": _f(item, "debtToEquity"),
                    "fcf_margin": _f_pct(item, "freeCashFlowMargin"),
                    "eps_chf": _f(item, "eps"),
                    "eps_growth_yoy": None,
                    "revenue_growth": None,
                    "dividend_yield": _f(item, "dividendYield"),
                    "dividend_growth": None,
                    "market_cap_chf": _f(item, "marketCap"),
                    "sector": None,
                    "source": "fmp",
                }
            )

        log.info("FMP %s: %d Quartale", symbol, len(rows))
        return rows


def _f(d: dict[str, Any], key: str) -> float | None:
    v = d.get(key)
    if v is None or v == "" or v == 0:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _f_pct(d: dict[str, Any], key: str) -> float | None:
    """FMP gibt Quoten als Dezimal (0.15 = 15%) — in Prozent umrechnen."""
    v = _f(d, key)
    return v * 100 if v is not None else None
