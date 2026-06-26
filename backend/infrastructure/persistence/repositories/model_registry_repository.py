"""SQLA Repository für model_registry (V4-6 Champion/Challenger)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.jobs.retraining_job import ModelRecord
from backend.infrastructure.persistence.models.model_registry import ModelRegistryORM


class SQLAModelRegistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_champion(self, model_name: str) -> ModelRecord | None:
        stmt = select(ModelRegistryORM).where(
            ModelRegistryORM.model_name == model_name,
            ModelRegistryORM.is_champion.is_(True),
        )
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_record(row)

    async def insert(self, record: ModelRecord) -> None:
        orm = ModelRegistryORM(
            id=record.id,
            model_name=record.model_name,
            version=record.version,
            model_type=record.model_type,
            oos_r2=record.oos_r2,
            is_champion=record.is_champion,
            trained_at=record.trained_at,
            activated_at=record.activated_at,
            deactivated_at=record.deactivated_at,
            metadata_json=record.metadata_json,
        )
        self._session.add(orm)
        await self._session.flush()

    async def set_champion(
        self, new_champion_id: uuid.UUID, old_champion_id: uuid.UUID | None
    ) -> None:
        now = datetime.now(tz=UTC)
        if old_champion_id is not None:
            await self._session.execute(
                update(ModelRegistryORM)
                .where(ModelRegistryORM.id == old_champion_id)
                .values(is_champion=False, deactivated_at=now)
            )
        await self._session.execute(
            update(ModelRegistryORM)
            .where(ModelRegistryORM.id == new_champion_id)
            .values(is_champion=True, activated_at=now)
        )

    def _to_record(self, orm: ModelRegistryORM) -> ModelRecord:
        return ModelRecord(
            id=orm.id,
            model_name=orm.model_name,
            version=orm.version,
            model_type=orm.model_type,
            oos_r2=orm.oos_r2,
            is_champion=orm.is_champion,
            trained_at=orm.trained_at,
            activated_at=orm.activated_at,
            deactivated_at=orm.deactivated_at,
            metadata_json=orm.metadata_json,
        )
