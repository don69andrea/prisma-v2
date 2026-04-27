"""SQLAlchemy-Implementierung des UniverseRepository-Ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.universe import Universe
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.infrastructure.persistence.models.universe import UniverseORM


class SQLAUniverseRepository(UniverseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, universe_id: UUID) -> Universe | None:
        row = await self._session.get(UniverseORM, universe_id)
        return self._to_domain(row) if row else None

    async def list(self) -> list[Universe]:
        result = await self._session.execute(select(UniverseORM).order_by(UniverseORM.name))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, universe: Universe) -> None:
        row = await self._session.get(UniverseORM, universe.id)
        if row is None:
            self._session.add(
                UniverseORM(
                    id=universe.id,
                    name=universe.name,
                    region=universe.region,
                    tickers=list(universe.tickers),
                )
            )
        else:
            row.name = universe.name
            row.region = universe.region
            row.tickers = list(universe.tickers)

    @staticmethod
    def _to_domain(orm: UniverseORM) -> Universe:
        return Universe(
            id=orm.id,
            name=orm.name,
            region=orm.region,
            tickers=tuple(orm.tickers),
        )
