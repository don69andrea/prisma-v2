"""Abstraktes Repository-Interface für Stock-Entitäten (Port, nicht Adapter)."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.stock import Stock


class StockRepository(ABC):
    """Definiert den Vertrag zwischen Application-Layer und Persistence-Adapter.

    Konkrete Implementierungen leben ausschliesslich im Infrastructure-Layer.
    """

    @abstractmethod
    async def list(self, limit: int, offset: int) -> list[Stock]:
        """Gibt eine paginierte Liste aller Stocks zurück."""
        ...

    @abstractmethod
    async def get_by_ticker(self, ticker: str) -> Stock | None:
        """Sucht eine Stock-Entity anhand des Ticker-Symbols.

        Gibt None zurück wenn kein Treffer gefunden wurde (kein Exception-Missbrauch).
        """
        ...

    @abstractmethod
    async def get(self, stock_id: UUID) -> Stock | None:
        """Sucht eine Stock-Entity anhand ihrer UUID.

        Gibt None zurück wenn kein Treffer gefunden wurde (kein Exception-Missbrauch).
        """
        ...
