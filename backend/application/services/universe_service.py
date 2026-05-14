"""UniverseService — Use-Case-Orchestrierung für Universe-CRUD."""

import uuid

from backend.domain.entities.universe import Universe
from backend.domain.repositories.universe_repository import UniverseRepository


class UniverseNotFound(Exception):
    pass


class UniverseService:
    """Kapselt die Geschäftslogik rund um Universe-Operationen.

    Kennt nur den abstrakten UniverseRepository-Port.
    """

    def __init__(self, repository: UniverseRepository) -> None:
        self._repository = repository

    async def list_universes(self) -> list[Universe]:
        return await self._repository.list()

    async def get_universe(self, universe_id: uuid.UUID) -> Universe:
        result = await self._repository.get(universe_id)
        if result is None:
            raise UniverseNotFound(f"Universum {universe_id} nicht gefunden")
        return result

    async def create_universe(
        self,
        name: str,
        region: str,
        tickers: list[str],
    ) -> Universe:
        universe = Universe(
            id=uuid.uuid4(),
            name=name,
            region=region,
            tickers=tuple(tickers),
        )
        await self._repository.save(universe)
        return universe
