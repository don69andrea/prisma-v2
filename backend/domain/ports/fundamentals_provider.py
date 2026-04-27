"""Port für Fundamentaldaten-Lieferanten (yfinance, FMP, Stub)."""

from abc import ABC, abstractmethod

from backend.domain.models.quality_classic import UniverseData


class FundamentalsProvider(ABC):
    @abstractmethod
    async def get_fundamentals(self, tickers: list[str]) -> UniverseData: ...
