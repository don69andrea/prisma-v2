"""SQLAlchemy-Implementierung des RankingRunRepository-Ports."""

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.infrastructure.persistence.models.ranking_run import RankingRunORM


class SQLARankingRunRepository(RankingRunRepository):
    """SQLAlchemy-Implementierung des RankingRunRepository-Ports."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, run_id: UUID) -> RankingRun | None:
        row = await self._session.get(RankingRunORM, run_id)
        return self._to_domain(row) if row else None

    async def save(self, run: RankingRun) -> None:
        stmt = (
            pg_insert(RankingRunORM)
            .values(
                id=run.id,
                created_at=run.created_at,
                universe_id=run.universe_id,
                weight_config=run.weight_config.weights,
                status=run.status,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"status": run.status, "weight_config": run.weight_config.weights},
            )
        )
        await self._session.execute(stmt)

    async def list_by_universe(self, universe_id: UUID) -> list[RankingRun]:
        stmt = (
            select(RankingRunORM)
            .where(RankingRunORM.universe_id == universe_id)
            .order_by(RankingRunORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[RankingRun]:
        stmt = (
            select(RankingRunORM)
            .order_by(RankingRunORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save_results(self, run_id: UUID, results: list[dict[str, Any]]) -> None:
        row = await self._session.get(RankingRunORM, run_id)
        if row is not None:
            row.results = results

    async def get_results(self, run_id: UUID) -> list[dict[str, Any]] | None:
        row = await self._session.get(RankingRunORM, run_id)
        return row.results if row else None

    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        # JSONB-Array-Expansion: jsonb_array_elements liefert je einen Row pro Element.
        # Wir filtern auf completed Runs + passenden Ticker und nehmen den neuesten.
        stmt = text("""
            SELECT elem
            FROM ranking_runs,
                 jsonb_array_elements(results) AS elem
            WHERE status = 'completed'
              AND results IS NOT NULL
              AND elem->>'ticker' = :ticker
            ORDER BY created_at DESC
            LIMIT 1
        """)
        result = await self._session.execute(stmt, {"ticker": ticker.upper()})
        row = result.scalar_one_or_none()
        return dict(row) if row is not None else None

    @staticmethod
    def _to_domain(orm: RankingRunORM) -> RankingRun:
        return RankingRun(
            id=orm.id,
            created_at=orm.created_at,
            universe_id=orm.universe_id,
            weight_config=WeightConfig(weights=orm.weight_config),
            status=orm.status,  # type: ignore[arg-type]
        )
