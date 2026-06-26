"""YFinance-basierter Adapter für MarketDataProvider-Port.

Liefert 504 Handelstage Schlusskurse für SMI/SMIM-Tickers via yfinance.download().
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd
import yfinance as yf

from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

_logger = logging.getLogger(__name__)

_TRADING_DAYS = 504  # ~2 Jahre
_RETRIES = 2
_BASE_DELAY = 1.0


class YFinanceMarketDataAdapter(MarketDataProvider):
    """Implementiert MarketDataProvider via yfinance.download() für Swiss tickers."""

    def __init__(self) -> None:
        self._swiss = YFinanceSwissAdapter()

    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame()

        yf_tickers = [self._swiss.build_yf_ticker(t) for t in tickers]
        ticker_map = dict(zip(yf_tickers, tickers, strict=True))

        for attempt in range(_RETRIES + 1):
            try:
                raw: pd.DataFrame = await asyncio.to_thread(self._sync_download, yf_tickers)
                break
            except Exception as exc:
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "yfinance.download Versuch %d/%d fehlgeschlagen: %s — retry in %.1fs",
                        attempt + 1,
                        _RETRIES + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    _logger.error("yfinance.download endgültig fehlgeschlagen: %s", exc)
                    return pd.DataFrame()

        # yfinance.download mit mehreren Tickern liefert MultiIndex-Spalten
        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" in raw.columns.get_level_values(0):
                raw = raw["Close"]
            else:
                return pd.DataFrame()

        # Rename .SW back to PRISMA tickers
        raw = raw.rename(columns=ticker_map)
        raw = raw[[t for t in tickers if t in raw.columns]]

        # Ensure UTC-aware DatetimeIndex
        if raw.index.tz is None:
            raw.index = raw.index.tz_localize("UTC")
        else:
            raw.index = raw.index.tz_convert("UTC")

        return raw.tail(_TRADING_DAYS).dropna(how="all")

    @staticmethod
    def _sync_download(yf_tickers: list[str]) -> pd.DataFrame:
        return yf.download(
            yf_tickers,
            period="4y",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
