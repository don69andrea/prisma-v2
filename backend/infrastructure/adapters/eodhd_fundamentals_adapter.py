"""EODHD Fundamentals-Adapter — Point-in-Time CH-Fundamentals.

Free-Tier ist knapp (20 Calls/Tag); für den Seed ggf. 1 Monat Paid.
Leerer Key => Adapter deaktiviert (kein HTTP-Call, kein Boot-Fehler) — wie
der bestehende FMP-Adapter.

EODHD-Endpoint: GET https://eodhd.com/api/fundamentals/{TICKER}.{EXCHANGE}
  Swiss-Ticker-Mapping: NESN -> NESN.SW (EODHD nutzt .SW für SIX)
  Liefert Financials::Income_Statement / Balance_Sheet / Cash_Flow (quarterly)
  mit `filing_date` => das ist die PIT-Wahrheit (publish_date).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

log = logging.getLogger(__name__)

_BASE = "https://eodhd.com/api/fundamentals"


class EodhdFundamentalsAdapter:
    def __init__(self, api_key: str) -> None:
        self._key = api_key
        self.enabled = bool(api_key) and api_key not in ("your-eodhd-key", "change-me")

    @staticmethod
    def to_symbol(ticker: str) -> str:
        """NESN -> NESN.SW. Schon-suffixierte Ticker bleiben."""
        if "." in ticker:
            return ticker
        return f"{ticker}.SW"

    async def fetch_quarterly(self, ticker: str) -> list[dict[str, Any]]:
        """Liefert eine Liste PIT-korrekter Quartals-Fundamentals als Dicts,
        bereit für stock_fundamentals (Schema 0032). Leere Liste wenn
        deaktiviert oder keine Coverage."""
        if not self.enabled:
            log.info("EODHD deaktiviert (kein Key) — leere Coverage für %s", ticker)
            return []

        symbol = self.to_symbol(ticker)
        url = f"{_BASE}/{symbol}"
        params = {"api_token": self._key, "fmt": "json"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                log.warning("EODHD %s -> HTTP %s (keine Coverage?)", symbol, resp.status_code)
                return []
            data = resp.json()

        fin = data.get("Financials") or {}
        income = (fin.get("Income_Statement") or {}).get("quarterly", {})
        balance = (fin.get("Balance_Sheet") or {}).get("quarterly", {})
        cash = (fin.get("Cash_Flow") or {}).get("quarterly", {})
        highlights = data.get("Highlights") or {}
        general = data.get("General") or {}
        sector = general.get("Sector")

        rows: list[dict[str, Any]] = []
        for period_end, inc in income.items():
            bal = balance.get(period_end, {})
            cf = cash.get(period_end, {})
            rows.append(self._derive(ticker, period_end, inc, bal, cf, highlights, sector))
        log.info("EODHD %s: %d Quartale", symbol, len(rows))
        return rows

    @staticmethod
    def _f(d: dict[str, Any], key: str) -> float | None:
        v: Any = d.get(key)
        if v is None or v == "":
            return None
        if v == "0":
            return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _derive(
        self,
        ticker: str,
        period_end: str,
        inc: dict[str, Any],
        bal: dict[str, Any],
        cf: dict[str, Any],
        hi: dict[str, Any],
        sector: str | None,
    ) -> dict[str, Any]:
        """Berechnet abgeleitete Kennzahlen. publish_date = filing_date (PIT!)."""
        net_income = self._f(inc, "netIncome")
        revenue = self._f(inc, "totalRevenue")
        equity = self._f(bal, "totalStockholderEquity")
        debt = self._f(bal, "shortLongTermDebtTotal") or self._f(bal, "totalDebt")
        fcf = self._f(cf, "freeCashFlow")
        filing = inc.get("filing_date") or inc.get("date")
        return {
            "ticker": ticker,
            "period_end": date.fromisoformat(period_end),
            "publish_date": date.fromisoformat(filing) if filing else None,
            "period_type": "quarterly",
            "pe_ratio": self._f(hi, "PERatio"),
            "pb_ratio": None,  # ggf. aus Preis/Buchwert separat (siehe simfin_adapter Doku)
            "ev_ebitda": self._f(hi, "EnterpriseValueEbitda"),
            "roe": (net_income / equity * 100) if net_income and equity else None,
            "debt_equity": (debt / equity) if debt and equity else None,
            "fcf_margin": (fcf / revenue * 100) if fcf and revenue else None,
            "eps_chf": self._f(inc, "epsActual") or self._f(hi, "EarningsShare"),
            "eps_growth_yoy": None,  # im Feature-Builder aus q vs q-4 berechnen
            "revenue_growth": None,
            "dividend_yield": self._f(hi, "DividendYield"),
            "dividend_growth": None,
            "market_cap_chf": self._f(hi, "MarketCapitalization"),
            "sector": sector,
            "source": "eodhd",
        }
