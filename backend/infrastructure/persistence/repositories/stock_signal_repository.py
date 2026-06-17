from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.stock_signal_record import StockSignalRecord
from backend.domain.repositories.stock_signal_repository import StockSignalRepository as Port
from backend.infrastructure.persistence.models.stock_daily_signal import StockDailySignalORM


class SQLAStockSignalRepository(Port):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: StockSignalRecord) -> None:
        existing = await self._session.execute(
            select(StockDailySignalORM).where(
                StockDailySignalORM.ticker == record.ticker,
                StockDailySignalORM.snapshot_date == record.snapshot_date,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            row.signal = record.signal
            row.weighted_score = record.weighted_score
            row.quant_score = record.quant_score
            row.ml_score = record.ml_score
            row.macro_score = record.macro_score
            row.confidence = record.confidence
            row.is_3a_eligible = record.is_3a_eligible
        else:
            self._session.add(
                StockDailySignalORM(
                    id=str(uuid.uuid4()),
                    ticker=record.ticker,
                    snapshot_date=record.snapshot_date,
                    signal=record.signal,
                    weighted_score=record.weighted_score,
                    quant_score=record.quant_score,
                    ml_score=record.ml_score,
                    macro_score=record.macro_score,
                    confidence=record.confidence,
                    is_3a_eligible=record.is_3a_eligible,
                )
            )

    async def get_today(self, ticker: str) -> StockSignalRecord | None:
        today = datetime.now(UTC).date()
        result = await self._session.execute(
            select(StockDailySignalORM).where(
                StockDailySignalORM.ticker == ticker.upper(),
                StockDailySignalORM.snapshot_date == today,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_today_all(self) -> list[StockSignalRecord]:
        today = datetime.now(UTC).date()
        result = await self._session.execute(
            select(StockDailySignalORM).where(StockDailySignalORM.snapshot_date == today)
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    @staticmethod
    def _to_domain(row: StockDailySignalORM) -> StockSignalRecord:
        return StockSignalRecord(
            id=row.id,
            ticker=row.ticker,
            snapshot_date=row.snapshot_date,
            signal=row.signal,
            weighted_score=row.weighted_score,
            quant_score=row.quant_score,
            ml_score=row.ml_score,
            macro_score=row.macro_score,
            confidence=row.confidence,
            is_3a_eligible=row.is_3a_eligible,
            created_at=row.created_at,
        )
