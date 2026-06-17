from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.models.stock_signal_record import StockSignalRecord


class StockSignalRepository(ABC):
    @abstractmethod
    async def save(self, record: StockSignalRecord) -> None:
        """Upsert: ein Snapshot pro Ticker pro Kalendertag."""

    @abstractmethod
    async def get_today(self, ticker: str) -> StockSignalRecord | None:
        """Heutiger Snapshot für einen Ticker oder None."""

    @abstractmethod
    async def get_today_all(self) -> list[StockSignalRecord]:
        """Alle heutigen Snapshots (für Bulk-Antwort auf /decisions)."""
