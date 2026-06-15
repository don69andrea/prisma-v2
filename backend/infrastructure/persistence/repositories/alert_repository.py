"""SQLAlchemy-Implementierung des AlertRepository-Ports."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.alert import Alert
from backend.domain.repositories.alert_repository import AlertRepository
from backend.infrastructure.persistence.models.alert import AlertORM


class SQLAAlertRepository(AlertRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, alert: Alert) -> None:
        orm = self._to_orm(alert)
        await self._session.merge(orm)

    async def get_by_id(self, alert_id: UUID) -> Alert | None:
        result = await self._session.execute(select(AlertORM).where(AlertORM.id == alert_id))
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def list_active(self) -> list[Alert]:
        result = await self._session.execute(
            select(AlertORM).where(AlertORM.is_active == True)  # noqa: E712
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    async def list_by_owner(self, target: str) -> list[Alert]:
        result = await self._session.execute(select(AlertORM).where(AlertORM.target == target))
        return [self._to_domain(r) for r in result.scalars().all()]

    async def delete(self, alert_id: UUID) -> None:
        await self._session.execute(delete(AlertORM).where(AlertORM.id == alert_id))

    async def update(self, alert: Alert) -> None:
        await self.save(alert)

    @staticmethod
    def _to_orm(a: Alert) -> AlertORM:
        return AlertORM(
            id=a.id,
            ticker=a.ticker,
            trigger_type=a.trigger_type,
            threshold=a.threshold,
            channel=a.channel,
            target=a.target,
            is_active=a.is_active,
            created_at=a.created_at,
            last_triggered_at=a.last_triggered_at,
            last_signal=a.last_signal,
            baseline_price=a.baseline_price,
        )

    @staticmethod
    def _to_domain(r: AlertORM) -> Alert:
        return Alert(
            id=r.id,
            ticker=r.ticker,
            trigger_type=r.trigger_type,  # type: ignore[arg-type]
            threshold=r.threshold,
            channel=r.channel,  # type: ignore[arg-type]
            target=r.target,
            is_active=r.is_active,
            created_at=r.created_at,
            last_triggered_at=r.last_triggered_at,
            last_signal=r.last_signal,
            baseline_price=r.baseline_price,
        )
