"""Abstraktes Repository-Interface für BacktestResult-Entitäten (Port)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.backtest_result import BacktestResult


class BacktestResultRepository(ABC):
    """Definiert den Vertrag zwischen Application-Layer und Persistence-Adapter.

    Konkrete Implementierungen leben ausschliesslich im Infrastructure-Layer.
    """

    @abstractmethod
    async def save(self, result: BacktestResult) -> None:
        """Speichert eine BacktestResult-Entity."""
        ...

    @abstractmethod
    async def get(self, result_id: UUID) -> BacktestResult | None:
        """Sucht eine BacktestResult-Entity anhand ihrer UUID.

        Gibt None zurück wenn kein Treffer gefunden wurde (kein Exception-Missbrauch).
        """
        ...
