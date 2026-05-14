"""Abstraktes Repository-Interface für RankingRun-Aggregate."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from backend.domain.entities.ranking_run import RankingRun


class RankingRunRepository(ABC):
    @abstractmethod
    async def get(self, run_id: UUID) -> RankingRun | None: ...

    @abstractmethod
    async def save(self, run: RankingRun) -> None: ...

    @abstractmethod
    async def list_by_universe(self, universe_id: UUID) -> list[RankingRun]: ...

    @abstractmethod
    async def save_results(self, run_id: UUID, results: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    async def get_results(self, run_id: UUID) -> list[dict[str, Any]] | None: ...

    @abstractmethod
    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        """Gibt das Ranking-Ergebnis für einen Ticker aus dem neuesten abgeschlossenen Run zurück.

        Gibt None zurück wenn kein completed Run mit diesem Ticker existiert.
        """
        ...
