"""yFinance-Adapter für Krypto-OHLCV und technische Indikatoren (pandas/numpy)."""

from __future__ import annotations

import asyncio
import logging

import pandas as pd
import yfinance as yf
from cachetools import TTLCache

_logger = logging.getLogger(__name__)

_TECH_CACHE: TTLCache[tuple[str, int], pd.DataFrame] = TTLCache(maxsize=50, ttl=300)
_CHF_PAIRS = {"BTC-CHF", "ETH-CHF"}
# USDCHF=X = CHF pro 1 USD (~0.90). Zur Umrechnung USD->CHF wird MULTIPLIZIERT.
# Vorher fälschlich "CHFUSD=X" (USD pro CHF, ~1.12) -> Preise ~22% zu hoch.
_CHF_USD_RATE_TICKER = "USDCHF=X"
# Plausibler Bereich für "CHF pro USD"; ausserhalb -> Fallback (schützt vor Inversion).
_CHF_PER_USD_FALLBACK = 0.90
_CHF_PER_USD_MIN = 0.5
_CHF_PER_USD_MAX = 1.5


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bbands(
    close: pd.Series, length: int = 20, std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(length).mean()
    rolling_std = close.rolling(length).std(ddof=1)
    upper = mid + std * rolling_std
    lower = mid - std * rolling_std
    return upper, mid, lower


def _ema(close: pd.Series, length: int) -> pd.Series:
    return close.ewm(span=length, adjust=False).mean()


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    df["RSI_14"] = _rsi(close, 14)
    macd_line, signal_line, hist = _macd(close, 12, 26, 9)
    df["MACD_12_26_9"] = macd_line
    df["MACDs_12_26_9"] = signal_line
    df["MACDh_12_26_9"] = hist
    bbu, bbm, bbl = _bbands(close, 20, 2.0)
    df["BBU_20_2.0"] = bbu
    df["BBM_20_2.0"] = bbm
    df["BBL_20_2.0"] = bbl
    df["EMA_20"] = _ema(close, 20)
    df["EMA_50"] = _ema(close, 50)
    return df


class YFinanceCryptoAdapter:
    """Historische OHLCV + Technische Indikatoren für Kryptowährungen.

    Bevorzugt CHF-Pairs (BTC-CHF, ETH-CHF). Für USD-Pairs: automatische
    CHF-Umrechnung via USDCHF=X (CHF pro USD, ~0.90) mit Fallback 0.90.
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

        df = _add_indicators(df)
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

    async def get_ohlcv(
        self, ticker_yf: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame | None:
        """Rohe OHLCV-Daten ohne Indikatoren (für Pattern-Detection, uncached).

        `period="1y"` statt der sonst üblichen Tage-Anzahl, damit ein EMA200
        auf genügend Historie aufbaut (Pattern-Service braucht EMA20/50/200).
        """
        try:
            df = await asyncio.to_thread(
                yf.download,
                ticker_yf,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
        except Exception:
            _logger.warning("get_ohlcv fehlgeschlagen: %s", ticker_yf)
            return None
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        return df

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
        """CHF pro 1 USD (~0.90). Multiplikativer Faktor für USD->CHF."""
        df = await self._download(_CHF_USD_RATE_TICKER, 2)
        if df is None or df.empty:
            return _CHF_PER_USD_FALLBACK
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        rate = float(df["Close"].iloc[-1])
        # Guard gegen falsche Richtung/Ausreisser (z.B. versehentlich CHFUSD ~1.12).
        if not (_CHF_PER_USD_MIN <= rate <= _CHF_PER_USD_MAX):
            _logger.warning(
                "CHF/USD-Kurs %.4f ausserhalb Plausibilitaetsbereich — Fallback %.2f",
                rate,
                _CHF_PER_USD_FALLBACK,
            )
            return _CHF_PER_USD_FALLBACK
        return rate
