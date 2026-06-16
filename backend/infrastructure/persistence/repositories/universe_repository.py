"""SQLAlchemy-Implementierung des UniverseRepository-Ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.universe import Universe
from backend.domain.repositories.universe_repository import (
    DuplicateUniverseNameError,
    UniverseRepository,
)
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
        stmt = (
            pg_insert(UniverseORM)
            .values(
                id=universe.id,
                name=universe.name,
                region=universe.region,
                tickers=list(universe.tickers),
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": universe.name,
                    "region": universe.region,
                    "tickers": list(universe.tickers),
                },
            )
        )
        try:
            await self._session.execute(stmt)
        except IntegrityError as exc:
            # ON CONFLICT (id) greift nur bei PK-Kollisionen — create_universe()
            # generiert aber immer eine neue UUID, daher landet ein Namens-Duplikat
            # nie im Conflict-Handler, sondern als rohe IntegrityError hier.
            # Detection per Index-Name (ix_universes_name ist in Migration benannt) —
            # robust gegen Postgres-Error-Message-Aenderungen.
            if "ix_universes_name" in str(exc.orig):
                raise DuplicateUniverseNameError(universe.name) from exc
            raise

    @staticmethod
    def _to_domain(orm: UniverseORM) -> Universe:
        return Universe(
            id=orm.id,
            name=orm.name,
            region=orm.region,
            tickers=tuple(orm.tickers),
        )
