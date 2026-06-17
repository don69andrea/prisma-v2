from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.cron_run_record import CronRunRecord
from backend.domain.repositories.cron_run_repository import CronRunRepository as Port
from backend.infrastructure.persistence.models.cron_run_log import CronRunLogORM


class SQLACronRunRepository(Port):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_run(self, job_name: str) -> str:
        run_id = str(uuid.uuid4())
        self._session.add(
            CronRunLogORM(
                id=run_id,
                job_name=job_name,
                started_at=datetime.now(UTC),
                status="running",
            )
        )
        await self._session.commit()
        return run_id

    async def finish_run(
        self,
        run_id: str,
        status: str,
        records_saved: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        result = await self._session.execute(
            select(CronRunLogORM).where(CronRunLogORM.id == run_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.finished_at = datetime.now(UTC)
        row.status = status
        row.records_saved = records_saved
        row.error_msg = error_msg
        await self._session.commit()

    async def get_latest_per_job(self) -> list[CronRunRecord]:
        # Use ROW_NUMBER() window function so only one row per job_name is
        # fetched from the DB rather than the full table history.
        row_num = (
            func.row_number()
            .over(
                partition_by=CronRunLogORM.job_name,
                order_by=CronRunLogORM.started_at.desc(),
            )
            .cast(Integer)
            .label("rn")
        )
        subq = select(CronRunLogORM, row_num).subquery()
        result = await self._session.execute(
            select(CronRunLogORM).from_statement(select(subq).where(subq.c.rn == 1))
        )
        return [
            CronRunRecord(
                id=r.id,
                job_name=r.job_name,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                records_saved=r.records_saved,
                error_msg=r.error_msg,
            )
            for r in result.scalars().all()
        ]
