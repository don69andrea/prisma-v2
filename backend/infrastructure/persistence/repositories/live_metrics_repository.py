"""SQLA Repository für live_performance_metrics (V4-6)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.jobs.signal_evaluation_job import MetricsRecord
from backend.infrastructure.persistence.models.live_performance_metrics import (
    LivePerformanceMetricORM,
)


class SQLALiveMetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, record: MetricsRecord, computed_at: datetime) -> None:
        orm = LivePerformanceMetricORM(
            coin_id=record.coin_id,
            computed_at=computed_at,
            window_days=record.window_days,
            n_signals=record.n_signals,
            hit_rate=record.hit_rate,
            live_sharpe=record.live_sharpe,
            live_calmar=record.live_calmar,
            vol_mae=record.vol_mae,
        )
        self._session.add(orm)
        await self._session.flush()
