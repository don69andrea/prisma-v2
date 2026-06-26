"""SQLA Repository für drift_flags (V4-6 DriftMonitor)."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.jobs.drift_monitor import DriftFlag
from backend.infrastructure.persistence.models.drift_flags import DriftFlagORM


class SQLADriftFlagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, flag: DriftFlag) -> None:
        orm = DriftFlagORM(
            id=flag.id,
            coin=flag.coin,
            flagged_at=flag.flagged_at,
            metric_name=flag.metric_name,
            live_value=flag.live_value,
            expected_value=flag.expected_value,
            pct_deviation=flag.pct_deviation,
            is_active=flag.is_active,
            alert_sent=flag.alert_sent,
        )
        self._session.add(orm)
        await self._session.flush()

    async def list_active(self) -> list[DriftFlag]:
        stmt = select(DriftFlagORM).where(DriftFlagORM.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_flag(r) for r in result.scalars().all()]

    async def mark_alert_sent(self, flag_id: uuid.UUID) -> None:
        await self._session.execute(
            update(DriftFlagORM).where(DriftFlagORM.id == flag_id).values(alert_sent=True)
        )

    def _to_flag(self, orm: DriftFlagORM) -> DriftFlag:
        return DriftFlag(
            id=orm.id,
            coin=orm.coin,
            flagged_at=orm.flagged_at,
            metric_name=orm.metric_name,
            live_value=orm.live_value,
            expected_value=orm.expected_value,
            pct_deviation=orm.pct_deviation,
            is_active=orm.is_active,
            alert_sent=orm.alert_sent,
        )
