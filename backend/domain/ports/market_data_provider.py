"""Port für Markt-/Preis-Daten-Lieferanten (yfinance, FMP, Stub)."""

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        """Liefert Tagesschlusskurse für 504 Trading-Days bis zum letzten verfügbaren Tag.

        Returns:
            DataFrame mit:
            - Index: pd.DatetimeIndex, tz-aware (UTC), Business-Day-Frequenz
            - Columns: nur tickers, für die Daten verfügbar sind (Best-Effort)
            - Shape: 504 × N (N ≤ len(tickers))
            - Keine NaN in der Mitte; Anfang/Ende kann lückig sein wenn Ticker neu/delisted
            - Empty DataFrame wenn ``tickers=[]``
        """
        ...
