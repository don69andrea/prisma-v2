"""SQLAlchemy-Implementierung des CryptoSignalRepository-Ports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.crypto_signal_record import CryptoSignalRecord
from backend.domain.repositories.crypto_signal_repository import (
    CryptoSignalRepository as CryptoSignalRepositoryPort,
)
from backend.infrastructure.persistence.models.crypto_signal import CryptoSignalORM


class SQLACryptoSignalRepository(CryptoSignalRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: CryptoSignalRecord) -> None:
        """Upsert: ein Snapshot pro Ticker pro Kalendertag (UTC). Committed NICHT selbst
        — die aufrufende Session-Lifecycle-Schicht übernimmt das (siehe get_session())."""
        today = datetime.now(UTC).date()
        result = await self._session.execute(
            select(CryptoSignalORM).where(
                CryptoSignalORM.ticker == record.ticker,
                CryptoSignalORM.created_at
                >= datetime(today.year, today.month, today.day, tzinfo=UTC),
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.signal = record.signal
            existing.score = record.score
            existing.components = record.components
            existing.price_chf = record.price_chf
            existing.price_change_24h = record.price_change_24h
            existing.fear_greed_value = record.fear_greed_value
            existing.rsi_14 = record.rsi_14
            existing.macd_signal = record.macd_signal
            existing.volatility_30d_pct = record.volatility_30d_pct
            existing.detected_patterns = record.detected_patterns
            existing.pattern_score = record.pattern_score
            existing.agent_analysis = record.agent_analysis
        else:
            self._session.add(self._to_orm(record))

    async def get_history(self, ticker: str, days: int = 30) -> list[CryptoSignalRecord]:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(CryptoSignalORM)
            .where(CryptoSignalORM.ticker == ticker, CryptoSignalORM.created_at >= since)
            .order_by(CryptoSignalORM.created_at.asc())
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    async def get_latest_all(self) -> list[CryptoSignalRecord]:
        result = await self._session.execute(
            select(CryptoSignalORM).order_by(
                CryptoSignalORM.ticker, CryptoSignalORM.created_at.desc()
            )
        )
        latest_by_ticker: dict[str, CryptoSignalORM] = {}
        for row in result.scalars().all():
            latest_by_ticker.setdefault(row.ticker, row)
        return [self._to_domain(r) for r in latest_by_ticker.values()]

    @staticmethod
    def _to_orm(r: CryptoSignalRecord) -> CryptoSignalORM:
        return CryptoSignalORM(
            ticker=r.ticker,
            signal=r.signal,
            score=r.score,
            components=r.components,
            price_chf=r.price_chf,
            price_change_24h=r.price_change_24h,
            fear_greed_value=r.fear_greed_value,
            rsi_14=r.rsi_14,
            macd_signal=r.macd_signal,
            volatility_30d_pct=r.volatility_30d_pct,
            detected_patterns=r.detected_patterns,
            pattern_score=r.pattern_score,
            agent_analysis=r.agent_analysis,
        )

    @staticmethod
    def _to_domain(row: CryptoSignalORM) -> CryptoSignalRecord:
        return CryptoSignalRecord(
            id=str(row.id),
            ticker=row.ticker,
            signal=row.signal,
            score=row.score,
            components=row.components or {},
            price_chf=row.price_chf,
            price_change_24h=row.price_change_24h,
            fear_greed_value=row.fear_greed_value,
            rsi_14=row.rsi_14,
            macd_signal=row.macd_signal,
            volatility_30d_pct=row.volatility_30d_pct,
            detected_patterns=row.detected_patterns or [],
            pattern_score=row.pattern_score,
            agent_analysis=row.agent_analysis,
            created_at=row.created_at,
        )
