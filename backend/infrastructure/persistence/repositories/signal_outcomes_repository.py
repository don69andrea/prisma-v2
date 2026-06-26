"""SQLA Repository für signal_outcomes (V4-6)."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.jobs.signal_evaluation_job import OutcomeRecord
from backend.infrastructure.persistence.models.signal_outcomes import SignalOutcomeORM

_logger = logging.getLogger(__name__)


class SQLASignalOutcomeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_pending(self, asof: date) -> list[OutcomeRecord]:
        stmt = select(SignalOutcomeORM).where(SignalOutcomeORM.realized_fwd_return.is_(None))
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            OutcomeRecord(
                coin_id=r.coin_id,
                signal_date=r.signal_date,
                horizon=r.horizon,
                action=r.action,
                size_factor=r.size_factor,
                confidence=r.confidence,
                pred_vol=r.pred_vol,
                realized_fwd_return=r.realized_fwd_return,
            )
            for r in rows
        ]

    async def backfill_return(
        self, coin_id: int, signal_date: date, horizon: int, realized: float
    ) -> None:
        stmt = (
            update(SignalOutcomeORM)
            .where(
                SignalOutcomeORM.coin_id == coin_id,
                SignalOutcomeORM.signal_date == signal_date,
                SignalOutcomeORM.horizon == horizon,
            )
            .values(realized_fwd_return=realized)
        )
        await self._session.execute(stmt)

    async def list_resolved(self, coin_id: int, since: date) -> list[OutcomeRecord]:
        stmt = select(SignalOutcomeORM).where(
            SignalOutcomeORM.coin_id == coin_id,
            SignalOutcomeORM.signal_date >= since,
            SignalOutcomeORM.realized_fwd_return.is_not(None),
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            OutcomeRecord(
                coin_id=r.coin_id,
                signal_date=r.signal_date,
                horizon=r.horizon,
                action=r.action,
                size_factor=r.size_factor,
                confidence=r.confidence,
                pred_vol=r.pred_vol,
                realized_fwd_return=r.realized_fwd_return,
            )
            for r in rows
        ]

    async def insert(self, record: OutcomeRecord) -> SignalOutcomeORM:
        orm = SignalOutcomeORM(
            coin_id=record.coin_id,
            signal_date=record.signal_date,
            horizon=record.horizon,
            action=record.action,
            size_factor=record.size_factor,
            confidence=record.confidence,
            pred_vol=record.pred_vol,
            realized_fwd_return=record.realized_fwd_return,
        )
        self._session.add(orm)
        await self._session.flush()
        return orm
