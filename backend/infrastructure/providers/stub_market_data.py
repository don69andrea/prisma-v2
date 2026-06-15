"""Stub-Implementierung des MarketDataProvider für Demo und Tests.

Generiert pro Ticker einen deterministischen Random-Walk via zlib.crc32-Seed
(prozess-stabil, im Gegensatz zu builtin hash()). end_date injizierbar
für vollständig deterministische Tests.

Spec: docs/specs/2026-05-09-ranking-service-multi-model.md §"Stub-Adapter"
"""

import zlib

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from backend.domain.ports.market_data_provider import MarketDataProvider

_TRADING_DAYS: int = 504
_DRIFT: float = 0.0005
_VOLATILITY: float = 0.015
_START_PRICE: float = 100.0


class StubMarketDataProvider(MarketDataProvider):
    """Demo/Test-Provider mit deterministischem Random-Walk pro Ticker."""

    def __init__(self, end_date: pd.Timestamp | None = None) -> None:
        raw_end = end_date or pd.Timestamp.now(tz="UTC").normalize()
        # bdate_range(end=...) length differs by 1 across pandas 3.0.2 ↔ 3.0.3
        # when end falls on a weekend. Snap to prior business day for stability.
        self._end_date = BDay().rollback(raw_end)

    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame()

        index = pd.bdate_range(end=self._end_date, periods=_TRADING_DAYS, tz="UTC")

        data: dict[str, np.ndarray] = {}  # type: ignore[type-arg]
        for ticker in tickers:
            seed = zlib.crc32(ticker.encode("utf-8"))
            rng = np.random.default_rng(seed)
            returns = rng.normal(_DRIFT, _VOLATILITY, _TRADING_DAYS)
            prices = _START_PRICE * (1 + returns).cumprod()
            data[ticker] = prices

        return pd.DataFrame(data, index=index)
