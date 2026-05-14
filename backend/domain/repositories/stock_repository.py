"""Abstraktes Repository-Interface für Stock-Entitäten (Port, nicht Adapter)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.stock import Stock


class StockRepository(ABC):
    """Definiert den Vertrag zwischen Application-Layer und Persistence-Adapter.

    Konkrete Implementierungen leben ausschliesslich im Infrastructure-Layer.
    """

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

    @abstractmethod
    async def list_by_ids(self, stock_ids: list[UUID]) -> list[Stock]:
        """Bulk-Lookup ueber mehrere IDs in einer Query (vermeidet N+1).

        Reihenfolge ist NICHT garantiert; Caller soll fuer Lookup-Maps eine
        dict-Comprehension nutzen, nicht Index-Position.
        """
        ...

    @abstractmethod
    async def list_by_tickers(self, tickers: list[str]) -> list[Stock]:
        """Bulk-Lookup ueber mehrere Ticker in einer Query (vermeidet N+1).

        Tickers werden case-insensitive verglichen (intern via `upper()`).
        """
        ...

    @abstractmethod
    async def list(self, limit: int, offset: int) -> list[Stock]:
        """Gibt eine paginierte Liste aller Stocks zurück.

        Steht AM ENDE der Klasse: `list` als Methoden-Name shadowed den
        builtin in der Klassen-Scope, sodass `list[...]`-Annotationen NACH
        dieser Methode mypy-Errors werfen ("Function is not valid as a type").
        """
        ...
