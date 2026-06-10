"""Port für Swiss Market Data (yfinance-Adapter oder SIX-API)."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals


class SwissMarketDataProvider(ABC):
    @abstractmethod
    async def get_fundamentals(self, ticker: str) -> SwissFundamentals:
        """Gibt Fundamentaldaten für einen Swiss Stock zurück.

        Args:
            ticker: PRISMA-Ticker ohne .SW-Suffix (z.B. 'NESN')

        Raises:
            SwissDataUnavailableError: wenn yfinance keinen .SW-Ticker kennt
        """
        ...

    @abstractmethod
    async def get_price_history(self, ticker: str, days: int = 252) -> pd.DataFrame:
        """Liefert Tagesschlusskurse (CHF) für die letzten `days` Handelstage.

        Returns:
            DataFrame mit DatetimeIndex (UTC) und Spalten Close, Volume.
            Leerer DataFrame wenn keine Daten verfügbar.
        """
        ...

    @abstractmethod
    async def get_isin(self, ticker: str) -> str | None:
        """Ruft die ISIN direkt von yfinance ab.

        Nützlich für ISIN-Verifikation (Issue #26).
        Returns None wenn yfinance keine ISIN kennt.
        """
        ...
