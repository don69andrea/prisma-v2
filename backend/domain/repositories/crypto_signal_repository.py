"""Repository-Port für CryptoSignalRecord (historische Signal-Snapshots)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.models.crypto_signal_record import CryptoSignalRecord


class CryptoSignalRepository(ABC):
    @abstractmethod
    async def save(self, record: CryptoSignalRecord) -> None:
        """Upsert: ein Snapshot pro Ticker pro Kalendertag (UTC)."""
        ...

    @abstractmethod
    async def get_history(self, ticker: str, days: int = 30) -> list[CryptoSignalRecord]: ...

    @abstractmethod
    async def get_latest_all(self) -> list[CryptoSignalRecord]: ...
