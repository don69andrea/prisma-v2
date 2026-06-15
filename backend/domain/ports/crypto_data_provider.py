"""Port-Interface für Krypto-Datenquellen (Hexagonale Architektur)."""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class CryptoDataProvider(Protocol):
    """Abstraktion über alle externen Krypto-Datenquellen."""

    async def get_technicals(self, ticker_yf: str, days: int = 365) -> pd.DataFrame:
        """OHLCV + technische Indikatoren für ein Asset."""
        ...

    async def get_smi_correlation(self, ticker_yf: str, days: int = 365) -> float:
        """Korrelation zum SMI über `days` Tage (Pearson, -1 bis 1)."""
        ...
