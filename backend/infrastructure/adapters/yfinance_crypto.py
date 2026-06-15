"""yFinance-Adapter für Krypto-OHLCV und technische Indikatoren (pandas-ta)."""

from __future__ import annotations

import asyncio
import logging

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registriert DataFrame-Extension
import yfinance as yf
from cachetools import TTLCache

_logger = logging.getLogger(__name__)

_TECH_CACHE: TTLCache[tuple[str, int], pd.DataFrame] = TTLCache(maxsize=50, ttl=300)
_CHF_PAIRS = {"BTC-CHF", "ETH-CHF"}
_CHF_USD_RATE_TICKER = "CHFUSD=X"


class YFinanceCryptoAdapter:
    """Historische OHLCV + Technische Indikatoren für Kryptowährungen.

    Bevorzugt CHF-Pairs (BTC-CHF, ETH-CHF). Für USD-Pairs: automatische
    CHF-Umrechnung via CHFUSD=X mit Fallback 0.90.
    """

    async def get_technicals(self, ticker_yf: str, days: int = 365) -> pd.DataFrame:
        """Lädt OHLCV + RSI(14), MACD(12,26,9), BB(20,2), EMA(20,50)."""
        cache_key = (ticker_yf, days)
        if cache_key in _TECH_CACHE:
            return _TECH_CACHE[cache_key]

        df = await self._download(ticker_yf, days)
        if df is None or df.empty:
            usd_ticker = ticker_yf.replace("-CHF", "-USD")
            df = await self._download(usd_ticker, days)
            if df is not None and not df.empty:
                rate = await self._get_chf_usd_rate()
                df["Close"] = df["Close"] * rate
                df["Open"] = df["Open"] * rate
                df["High"] = df["High"] * rate
                df["Low"] = df["Low"] * rate

        if df is None or df.empty:
            _logger.warning("YFinanceCryptoAdapter: keine Daten für %s", ticker_yf)
            return pd.DataFrame()

        # Flatten MultiIndex-Columns (yfinance >= 0.2.40 gibt Tuple-Columns zurück)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.bbands(length=20, std=2.0, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)

        df = df.dropna(subset=["RSI_14", "MACD_12_26_9"])
        _TECH_CACHE[cache_key] = df
        return df

    async def get_smi_correlation(self, ticker_yf: str, days: int = 365) -> float:
        """Pearson-Korrelation zwischen Krypto und SMI über `days` Tage."""
        try:
            crypto_df, smi_df = await asyncio.gather(
                self._download(ticker_yf, days),
                self._download("^SSMI", days),
            )
            if crypto_df is None or crypto_df.empty or smi_df is None or smi_df.empty:
                return 0.0
            if isinstance(crypto_df.columns, pd.MultiIndex):
                crypto_df.columns = [col[0] for col in crypto_df.columns]
            if isinstance(smi_df.columns, pd.MultiIndex):
                smi_df.columns = [col[0] for col in smi_df.columns]
            combined = pd.DataFrame({"crypto": crypto_df["Close"], "smi": smi_df["Close"]}).dropna()
            return float(combined.corr().iloc[0, 1])
        except Exception:
            _logger.warning("SMI-Korrelation für %s nicht berechenbar", ticker_yf)
            return 0.0

    async def _download(self, ticker: str, days: int) -> pd.DataFrame | None:
        try:
            return await asyncio.to_thread(
                yf.download,
                ticker,
                period=f"{days}d",
                progress=False,
                auto_adjust=True,
            )
        except Exception:
            _logger.warning("yFinance Download fehlgeschlagen: %s", ticker)
            return None

    async def _get_chf_usd_rate(self) -> float:
        df = await self._download(_CHF_USD_RATE_TICKER, 2)
        if df is None or df.empty:
            return 0.90
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        return float(df["Close"].iloc[-1])
