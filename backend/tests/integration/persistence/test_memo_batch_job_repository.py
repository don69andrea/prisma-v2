"""Integration-Tests fuer SQLAMemoBatchJobRepository (echtes PG)."""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.infrastructure.persistence.repositories.memo_batch_job_repository import (
    SQLAMemoBatchJobRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _make_job(run_id: uuid.UUID, **overrides: object) -> MemoBatchJob:
    payload: dict[str, object] = {
        "id": uuid.uuid4(),
        "model_run_id": run_id,
        "top_n": 20,
        "language": "de",
        "status": "pending",
        "failed_stock_ids": [],
        "error_message": None,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
    }
    payload.update(overrides)
    return MemoBatchJob(**payload)  # type: ignore[arg-type]


@pytest_asyncio.fixture
async def seed_run(db_session: AsyncSession) -> uuid.UUID:
    """Erzeugt Universe + RankingRun, gibt run_id zurueck.

    Kein Stock noetig — memo_batch_jobs referenziert nur ranking_runs.
    """
    run_id = uuid.uuid4()
    universe_id = uuid.uuid4()

    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, region, tickers) "
            "VALUES (:id, 'BATCH_TEST', 'CH', ARRAY['ABBN']::varchar[])"
        ),
        {"id": universe_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO ranking_runs (id, universe_id, status, weight_config, created_at) "
            "VALUES (:id, :uid, 'completed', '{}', now())"
        ),
        {"id": run_id, "uid": universe_id},
    )
    await db_session.commit()
    return run_id


class TestRoundtripAndUpsert:
    @pytest.mark.usefixtures("truncate_memo_batch_jobs")
    async def test_save_then_get_returns_same_job(
        self,
        seed_run: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory)
        job = _make_job(seed_run)

        await repo.save(job)
        loaded = await repo.get(job.id)

        assert loaded is not None
        # Full entity equality — catches _orm_to_entity mapping drift on ALL fields
        assert loaded == job

    async def test_get_unknown_returns_none(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory)
        loaded = await repo.get(uuid.uuid4())
        assert loaded is None

    @pytest.mark.usefixtures("truncate_memo_batch_jobs")
    async def test_upsert_preserves_id_and_created_at(
        self,
        seed_run: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory)
        original = _make_job(seed_run)
        await repo.save(original)

        # Update mit gleicher id, neuem status + completed_at
        updated = original.model_copy(
            update={
                "status": "complete",
                "completed_at": datetime.now(UTC),
                "created_at": datetime.now(UTC),  # versuche zu ueberschreiben
            }
        )
        await repo.save(updated)

        loaded = await repo.get(original.id)
        assert loaded is not None
        assert loaded.status == "complete"
        # created_at darf NICHT veraendert sein (Lifecycle-Marker)
        assert loaded.created_at == original.created_at

    @pytest.mark.usefixtures("truncate_memo_batch_jobs")
    async def test_failed_stock_ids_jsonb_roundtrip(
        self,
        seed_run: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory)
        stock_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        job = _make_job(seed_run, failed_stock_ids=stock_ids, status="partial")
        await repo.save(job)

        loaded = await repo.get(job.id)
        assert loaded is not None
        assert loaded.failed_stock_ids == stock_ids
        # Full entity equality — verifies the complete roundtrip, not just failed_stock_ids
        assert loaded == job


class TestMigrationConstraintNames:
    """Verifiziert dass die Live-DB-Constraints nicht doppelt-praefixiert sind.

    Hintergrund: NAMING_CONVENTION in Base.metadata wendet
    `ck_%(table_name)s_%(constraint_name)s` auf jedes CheckConstraint-`name=`
    automatisch an. Wenn die Migration `name="ck_memo_batch_jobs_top_n"` setzt,
    entsteht in PG `ck_memo_batch_jobs_ck_memo_batch_jobs_top_n` (PR-#54-Bug).

    Der ORM-Test fuer Constraint-Namen lebt im Mapping-Layer, der dort korrekt
    ist; nur die Migration kann das Doubling verursachen — daher Test direkt
    gegen pg_constraint.
    """

    async def test_no_double_prefix_in_pg_constraint(self, db_session: AsyncSession) -> None:
        rows = await db_session.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'memo_batch_jobs'::regclass AND contype = 'c'"
            )
        )
        names = {r[0] for r in rows}
        assert names, "Expected at least one CHECK constraint on memo_batch_jobs"
        for name in names:
            assert "ck_memo_batch_jobs_ck_memo_batch_jobs" not in name, (
                f"Double-prefix in {name} (Migration setzt name= mit ck_<table>_-Praefix)"
            )

        expected = {
            "ck_memo_batch_jobs_top_n",
            "ck_memo_batch_jobs_language",
            "ck_memo_batch_jobs_status",
        }
        assert expected.issubset(names), f"Missing constraints: {expected - names}"
