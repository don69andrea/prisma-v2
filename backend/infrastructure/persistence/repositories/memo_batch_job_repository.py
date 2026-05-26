"""SQLAlchemy-Adapter fuer MemoBatchJobRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.domain.repositories.memo_batch_job_repository import (
    MemoBatchJobRepository,
)
from backend.infrastructure.persistence.models.memo_batch_job import (
    MemoBatchJobORM,
)


class SQLAMemoBatchJobRepository(MemoBatchJobRepository):
    """SQLAlchemy-Adapter mit eigener session_factory.

    Eigene Session pro Operation (analog SQLAResearchMemoRepository) —
    nicht an Request-Session gebunden, da Background-Worker auch
    persistieren.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, job: MemoBatchJob) -> None:
        async with self._session_factory() as session:
            insert_stmt = pg_insert(MemoBatchJobORM).values(
                id=job.id,
                model_run_id=job.model_run_id,
                top_n=job.top_n,
                language=job.language,
                status=job.status,
                failed_stock_ids=[str(uid) for uid in job.failed_stock_ids],
                expected_stock_ids=[str(uid) for uid in job.expected_stock_ids],
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": insert_stmt.excluded.status,
                    "failed_stock_ids": insert_stmt.excluded.failed_stock_ids,
                    "expected_stock_ids": insert_stmt.excluded.expected_stock_ids,
                    "error_message": insert_stmt.excluded.error_message,
                    "started_at": insert_stmt.excluded.started_at,
                    "completed_at": insert_stmt.excluded.completed_at,
                    # id und created_at bewusst NICHT im set_ — Lifecycle-Marker
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def get(self, job_id: UUID) -> MemoBatchJob | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(select(MemoBatchJobORM).where(MemoBatchJobORM.id == job_id))
            ).scalar_one_or_none()
            return _orm_to_entity(row) if row else None

    async def list_by_status(self, status: str) -> list[MemoBatchJob]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(MemoBatchJobORM).where(MemoBatchJobORM.status == status)
                    )
                )
                .scalars()
                .all()
            )
            return [_orm_to_entity(row) for row in rows]


def _orm_to_entity(row: MemoBatchJobORM) -> MemoBatchJob:
    """Mapping ORM-Row -> Domain-Entity. JSONB-Liste -> UUID-Liste."""
    return MemoBatchJob(
        id=row.id,
        model_run_id=row.model_run_id,
        top_n=row.top_n,
        language=row.language,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        failed_stock_ids=[UUID(str(s)) for s in row.failed_stock_ids],
        expected_stock_ids=[UUID(str(s)) for s in row.expected_stock_ids],
        error_message=row.error_message,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )
