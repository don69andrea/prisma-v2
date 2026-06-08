"""yfinance-Adapter für Schweizer Aktien (SIX Swiss Exchange, .SW-Suffix).

Implementiert SwissMarketDataProvider-Port.
yfinance ist synchron — alle Aufrufe laufen via asyncio.to_thread.
Retry: 2x Exponential Backoff, kein externes Framework nötig.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf

from backend.domain.errors import SwissDataUnavailableError
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

_logger = logging.getLogger(__name__)

_RETRIES = 2
_BASE_DELAY = 1.0


class YFinanceSwissAdapter(SwissMarketDataProvider):
    """Adapter für Swiss Market Data via yfinance (.SW-Suffix für SIX-Tickers)."""

    def build_yf_ticker(self, ticker: str) -> str:
        """Konvertiert PRISMA-Ticker in yfinance-Format: 'NESN' → 'NESN.SW'."""
        return f"{ticker.upper()}.SW"

    async def get_fundamentals(self, ticker: str) -> SwissFundamentals:
        info = await self._fetch_info(ticker)
        market_cap = info.get("marketCap")
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
