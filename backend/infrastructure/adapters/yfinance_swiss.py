"""yfinance-Adapter für Schweizer Aktien (SIX Swiss Exchange, .SW-Suffix).

Implementiert SwissMarketDataProvider-Port.
yfinance ist synchron — alle Aufrufe laufen via asyncio.to_thread.
Retry: 2x Exponential Backoff, kein externes Framework nötig.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf

from backend.domain.errors import SwissDataUnavailableError
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.value_objects.dividend_data import DividendData, DividendEntry
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

_logger = logging.getLogger(__name__)

_RETRIES = 2
_BASE_DELAY = 1.0


class YFinanceSwissAdapter(SwissMarketDataProvider):
    """Adapter für Swiss Market Data via yfinance (.SW-Suffix für SIX-Tickers)."""

    # yfinance verwendet für einige SIX-Titel abweichende Ticker-Symbole
    _YF_OVERRIDES: dict[str, str] = {
        "ROG": "RO.SW",  # Roche Holding AG — yfinance nutzt RO statt ROG
    }

    def build_yf_ticker(self, ticker: str) -> str:
        """Konvertiert PRISMA-Ticker in yfinance-Format: 'NESN' → 'NESN.SW'."""
        t = ticker.upper()
        return self._YF_OVERRIDES.get(t, f"{t}.SW")

    async def get_fundamentals(self, ticker: str) -> SwissFundamentals:
        info = await self._fetch_info(ticker)
        market_cap = info.get("marketCap")

        if market_cap is None:
            # Fallback: compute market_cap from sharesOutstanding * price.
            # yfinance sometimes omits "marketCap" for SIX-listed (.SW) tickers
            # even though the constituent fields are present.
            shares = info.get("sharesOutstanding")
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if shares is not None and price is not None:
                market_cap = shares * price
                _logger.warning(
                    "%s: marketCap missing from yfinance — estimated from "
                    "sharesOutstanding (%.0f) × price (%.2f) = %.0f CHF",
                    ticker,
                    shares,
                    price,
                    market_cap,
                )
            else:
                _logger.warning(
                    "%s: marketCap unavailable and cannot be estimated "
                    "(sharesOutstanding=%s, price=%s) — market_cap_chf will be null",
                    ticker,
                    shares,
                    price,
                )

        return SwissFundamentals(
            market_cap_chf=Decimal(str(market_cap)) if market_cap is not None else None,
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
            dividend_yield=info.get("dividendYield"),
            eps_chf=info.get("trailingEps"),
        )

    async def get_price_history(self, ticker: str, days: int = 252) -> pd.DataFrame:
        if days <= 0:
            raise ValueError(f"days must be positive, got {days}")
        yf_ticker = self.build_yf_ticker(ticker)
        return await self._fetch_history(yf_ticker, days)

    async def get_isin(self, ticker: str) -> str | None:
        """Ruft die ISIN über yfinance ab.

        Bekannte Einschränkung: Yahoo Finance liefert für SIX-kotierte (.SW)
        Titel kein `isin`-Feld im info-Dict — diese Methode gibt daher immer
        None zurück. ISINs für SMI-Stocks müssen manuell via SIX Exchange
        (https://www.six-group.com) verifiziert werden.
        """
        info = await self._fetch_info(ticker)
        return info.get("isin")

    async def _fetch_info(self, ticker: str) -> dict[str, Any]:
        yf_ticker = self.build_yf_ticker(ticker)
        last_exc: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                info: dict[str, Any] = await asyncio.to_thread(self._sync_info, yf_ticker)
                if not info:
                    raise SwissDataUnavailableError(ticker)
                return info
            except SwissDataUnavailableError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "yfinance %s attempt %d/%d failed: %s — retry in %.1fs",
                        yf_ticker,
                        attempt + 1,
                        _RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    async def _fetch_history(self, yf_ticker: str, days: int) -> pd.DataFrame:
        last_exc: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                df: pd.DataFrame = await asyncio.to_thread(self._sync_history, yf_ticker, days)
                return df
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "yfinance history %s attempt %d/%d failed: %s — retry in %.1fs",
                        yf_ticker,
                        attempt + 1,
                        _RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    async def get_dividends(self, ticker: str) -> DividendData:
        """Ruft Dividendendaten via yfinance ab.

        Gibt ein DividendData-Objekt zurück; Felder können None sein wenn
        yfinance keine Daten liefert. Wirft SwissDataUnavailableError wenn
        der Ticker nicht gefunden wird.
        """
        yf_ticker = self.build_yf_ticker(ticker)
        info = await self._fetch_info(ticker)
        div_series = await self._fetch_dividends(yf_ticker)

        ex_ts = info.get("exDividendDate")
        ex_date: str | None = None
        if ex_ts is not None:
            ex_date = datetime.fromtimestamp(float(ex_ts), tz=UTC).strftime("%Y-%m-%d")

        raw_yield = info.get("dividendYield")
        dividend_yield_pct: float | None = round(float(raw_yield) * 100, 2) if raw_yield else None

        last_val = info.get("lastDividendValue")
        last_dividend_chf: float | None = float(last_val) if last_val is not None else None

        history: list[DividendEntry] = []
        if not div_series.empty:
            for ts, amount in div_series.tail(10).items():
                date_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
                history.append(DividendEntry(date=date_str, amount_chf=round(float(amount), 4)))

        return DividendData(
            ticker=ticker.upper(),
            last_dividend_chf=last_dividend_chf,
            ex_date=ex_date,
            dividend_yield_pct=dividend_yield_pct,
            history=tuple(history),
            disclaimer=(
                "Dividendendaten via Yahoo Finance. Keine Anlageberatung. "
                "Historische Ausschüttungen garantieren keine zukünftigen Zahlungen."
            ),
        )

    async def _fetch_dividends(self, yf_ticker: str) -> pd.Series:
        last_exc: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                series: pd.Series = await asyncio.to_thread(self._sync_dividends, yf_ticker)
                return series
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "yfinance dividends %s attempt %d/%d failed: %s — retry in %.1fs",
                        yf_ticker,
                        attempt + 1,
                        _RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _sync_info(yf_ticker: str) -> dict[str, Any]:
        return dict(yf.Ticker(yf_ticker).info)

    @staticmethod
    def _sync_history(yf_ticker: str, days: int) -> pd.DataFrame:
        df = yf.Ticker(yf_ticker).history(period=f"{days}d")
        if df.empty:
            return pd.DataFrame()
        try:
            return df[["Close", "Volume"]]
        except KeyError:
            return pd.DataFrame()

    @staticmethod
    def _sync_dividends(yf_ticker: str) -> pd.Series:
        result: pd.Series = yf.Ticker(yf_ticker).dividends
        return result
