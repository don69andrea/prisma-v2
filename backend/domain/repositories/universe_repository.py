"""Abstraktes Repository-Interface für Universe-Entitäten."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.universe import Universe


class UniverseRepository(ABC):
    @abstractmethod
    async def get(self, universe_id: UUID) -> Universe | None: ...

    @abstractmethod
    async def list(self) -> list[Universe]: ...

    @abstractmethod
    async def save(self, universe: Universe) -> None: ...
