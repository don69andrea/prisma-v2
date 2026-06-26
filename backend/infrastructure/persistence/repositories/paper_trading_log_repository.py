"""SQLA Repository für paper_trading_log (V4-6b, append-only)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.jobs.paper_trading_log import PaperLogEntry
from backend.infrastructure.persistence.models.paper_trading_log import PaperTradingLogORM


class SQLAPaperTradingLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, entry: PaperLogEntry) -> None:
        orm = PaperTradingLogORM(
            id=entry.id,
            coin=entry.coin,
            signal_date=entry.signal_date,
            action=entry.action,
            size_factor=entry.size_factor,
            confidence=entry.confidence,
            pred_vol=entry.pred_vol,
            realized_fwd_return=entry.realized_fwd_return,
            written_at=entry.written_at,
        )
        self._session.add(orm)
        await self._session.flush()

    async def list_pending_outcomes(self, asof: date) -> list[PaperLogEntry]:
        stmt = select(PaperTradingLogORM).where(
            PaperTradingLogORM.realized_fwd_return.is_(None),
            PaperTradingLogORM.signal_date <= asof,
        )
        result = await self._session.execute(stmt)
        return [self._to_entry(r) for r in result.scalars().all()]

    async def backfill_return(self, entry_id: uuid.UUID, realized: float) -> None:
        await self._session.execute(
            update(PaperTradingLogORM)
            .where(PaperTradingLogORM.id == entry_id)
            .values(realized_fwd_return=realized)
        )

    async def list_all(
        self, coin: str | None = None, since: date | None = None
    ) -> list[PaperLogEntry]:
        stmt = select(PaperTradingLogORM)
        if coin is not None:
            stmt = stmt.where(PaperTradingLogORM.coin == coin)
        if since is not None:
            stmt = stmt.where(PaperTradingLogORM.signal_date >= since)
        stmt = stmt.order_by(PaperTradingLogORM.signal_date.desc())
        result = await self._session.execute(stmt)
        return [self._to_entry(r) for r in result.scalars().all()]

    def _to_entry(self, orm: PaperTradingLogORM) -> PaperLogEntry:
        return PaperLogEntry(
            id=orm.id,
            coin=orm.coin,
            signal_date=orm.signal_date,
            action=orm.action,
            size_factor=orm.size_factor,
            confidence=orm.confidence,
            pred_vol=orm.pred_vol,
            realized_fwd_return=orm.realized_fwd_return,
            written_at=orm.written_at,
        )
