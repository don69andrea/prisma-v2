"""OperationsPriceAdapter: verbindet CryptoPriceAdapter mit den Operations-Worker-Protokollen.

Zwei Adapter:
- EvalPriceAdapter:   get_close(coin_id: int, asof) → erfüllt SignalEvaluationJob.PriceProvider
- SymbolPriceAdapter: get_close(coin: str, asof) + get_history(coins, asof)
                      → erfüllt PaperTradingLogWriter.PriceProvider + RetrainingJob.PriceProvider

OHLCV-Daten werden pro Symbol für die Lebensdauer der Adapter-Instanz gecacht.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter

_logger = logging.getLogger(__name__)
_START_DATE = "2020-01-01"


def _lookup_close(df: pd.DataFrame, asof: date) -> float | None:
    """Gibt den Close-Preis am oder vor asof zurück."""
    if df.empty or "close" not in df.columns:
        return None
    asof_ts = pd.Timestamp(asof)
    candidates = df[df.index <= asof_ts]
    if candidates.empty:
        return None
    return float(candidates["close"].iloc[-1])


class EvalPriceAdapter:
    """Implementiert SignalEvaluationJob.PriceProvider mit echten OHLCV-Daten.

    coin_id_to_symbol: mappt DB-coin_id auf yfinance-Ticker (z.B. {1: "BTC-USD"}).
    Gecachte DataFrames bleiben für die Lebensdauer der Instanz erhalten.
    """

    def __init__(
        self,
        crypto_adapter: CryptoPriceAdapter,
        coin_id_to_symbol: dict[int, str],
    ) -> None:
        self._adapter = crypto_adapter
        self._coin_map = coin_id_to_symbol
        self._cache: dict[str, pd.DataFrame] = {}

    async def _get_df(self, symbol: str) -> pd.DataFrame:
        if symbol not in self._cache:
            self._cache[symbol] = await self._adapter.fetch_ohlcv(symbol, start=_START_DATE)
        return self._cache[symbol]

    async def get_close(self, coin_id: int, asof: date) -> float | None:
        symbol = self._coin_map.get(coin_id)
        if symbol is None:
            _logger.warning("Kein Symbol für coin_id=%d bekannt", coin_id)
            return None
        df = await self._get_df(symbol)
        return _lookup_close(df, asof)


class SymbolPriceAdapter:
    """Implementiert PaperTradingLogWriter.PriceProvider + RetrainingJob.PriceProvider.

    Beide Protokolle verwenden Coin-Symbole (str) statt coin_id.
    Gecachte DataFrames bleiben für die Lebensdauer der Instanz erhalten.
    """

    def __init__(self, crypto_adapter: CryptoPriceAdapter) -> None:
        self._adapter = crypto_adapter
        self._cache: dict[str, pd.DataFrame] = {}

    async def _get_df(self, symbol: str) -> pd.DataFrame:
        if symbol not in self._cache:
            self._cache[symbol] = await self._adapter.fetch_ohlcv(symbol, start=_START_DATE)
        return self._cache[symbol]

    async def get_close(self, coin: str, asof: date) -> float | None:
        df = await self._get_df(coin)
        return _lookup_close(df, asof)

    async def get_history(self, coins: list[str], asof: date) -> pd.DataFrame:
        """DataFrame mit Spalten=Coin-Symbole, Zeilen=Datum, Werte=Close-Preis bis asof."""
        asof_ts = pd.Timestamp(asof)
        frames: list[pd.DataFrame] = []
        for coin in coins:
            df = await self._get_df(coin)
            if df.empty or "close" not in df.columns:
                _logger.warning("Keine OHLCV-Daten für %s", coin)
                continue
            col = df[df.index <= asof_ts][["close"]].rename(columns={"close": coin})
            frames.append(col)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1)
