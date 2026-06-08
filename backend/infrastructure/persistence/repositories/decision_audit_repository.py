"""SQLA-Implementierung des DecisionAuditRepository."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.decision_audit_record import DecisionAuditRecord
from backend.domain.repositories.decision_audit_repository import DecisionAuditRepository
from backend.infrastructure.persistence.models.decision_audit_log import DecisionAuditLogORM


class SQLADecisionAuditRepository(DecisionAuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: DecisionAuditRecord) -> None:
        orm = DecisionAuditLogORM(
            id=record.id,
            ticker=record.ticker,
            signal=record.signal,
            weighted_score=record.weighted_score,
            quant_score=record.quant_score,
            ml_score=record.ml_score,
            macro_score=record.macro_score,
            is_3a_eligible=record.is_3a_eligible,
            snapshot_date=record.snapshot_date,
            computed_at=record.computed_at,
            explanation_de=record.explanation_de,
        )
        self._session.add(orm)
        await self._session.flush()

    async def list_by_ticker(self, ticker: str, limit: int = 10) -> list[DecisionAuditRecord]:
        stmt = (
            sa.select(DecisionAuditLogORM)
            .where(DecisionAuditLogORM.ticker == ticker.upper())
            .order_by(DecisionAuditLogORM.computed_at.desc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [_to_entity(row) for row in rows.scalars()]


def _to_entity(orm: DecisionAuditLogORM) -> DecisionAuditRecord:
    return DecisionAuditRecord(
        id=orm.id,
        ticker=orm.ticker,
        signal=orm.signal,
        weighted_score=orm.weighted_score,
        quant_score=orm.quant_score,
        ml_score=orm.ml_score,
        macro_score=orm.macro_score,
        is_3a_eligible=orm.is_3a_eligible,
        snapshot_date=orm.snapshot_date,
        computed_at=orm.computed_at,
        explanation_de=orm.explanation_de,
    )
