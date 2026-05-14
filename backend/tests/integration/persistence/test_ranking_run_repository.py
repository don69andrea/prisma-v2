"""Integration-Tests für SQLARankingRunRepository gegen Live-Postgres.

Fokus: doppelter save()-Aufruf in derselben Session (status running → completed)
und save() + save_results() + save()-Sequenz wie sie RankingRunService nutzt.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig
from backend.infrastructure.persistence.repositories.ranking_run_repository import (
    SQLARankingRunRepository,
)

pytestmark = [pytest.mark.integration]


@pytest_asyncio.fixture
async def truncate_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    """Per-Test-Cleanup für ranking_runs-Tabelle."""
    truncate_sql = text("TRUNCATE ranking_runs, universes, stocks CASCADE")
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()


@pytest_asyncio.fixture
async def seeded_universe(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_runs: None,
) -> uuid.UUID:
    universe_id = uuid.uuid4()
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO universes (id, name, region, tickers) "
                "VALUES (:id, :name, :region, :tickers)"
            ),
            {
                "id": str(universe_id),
                "name": "Test-Universe",
                "region": "US",
                "tickers": ["AAPL", "MSFT"],
            },
        )
        await session.commit()
    return universe_id


def _new_run(universe_id: uuid.UUID, status: str = "running") -> RankingRun:
    return RankingRun(
        id=uuid.uuid4(),
        created_at=datetime.now(tz=UTC),
        universe_id=universe_id,
        weight_config=WeightConfig(weights={"quality_classic": 1.0}),
        status=status,  # type: ignore[arg-type]
    )


async def test_save_twice_updates_instead_of_insert(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_universe: uuid.UUID,
) -> None:
    """Regression: zweiter save() mit gleicher ID muss UPDATE machen, nicht INSERT.

    Bug: bei autoflush=False findet session.get() die noch-pending Row vom ersten
    save() nicht → zweiter save() trifft den add-Pfad → INSERT mit Duplicate-PK.
    """
    run = _new_run(seeded_universe, status="running")

    async with session_factory() as session:
        repo = SQLARankingRunRepository(session)
        await repo.save(run)

        completed = run.model_copy(update={"status": "completed"})
        await repo.save(completed)

        await session.commit()

    # Verifikation in separater Session
    async with session_factory() as session:
        row = await SQLARankingRunRepository(session).get(run.id)
        assert row is not None
        assert row.status == "completed"


async def test_save_then_save_results_then_save_persists_all(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_universe: uuid.UUID,
) -> None:
    """Regression: save → save_results → save (Service-Call-Pattern) persistiert alles.

    Bug: save_results macht session.get() das die pending Row nicht findet → No-Op.
    Resultat: nach Commit fehlt sowohl der Status-Update als auch die Results.
    """
    run = _new_run(seeded_universe, status="running")
    results = [{"ticker": "AAPL", "total_rank": 1}]

    async with session_factory() as session:
        repo = SQLARankingRunRepository(session)
        await repo.save(run)
        await repo.save_results(run.id, results)
        completed = run.model_copy(update={"status": "completed"})
        await repo.save(completed)
        await session.commit()

    async with session_factory() as session:
        repo = SQLARankingRunRepository(session)
        row = await repo.get(run.id)
        loaded_results = await repo.get_results(run.id)

    assert row is not None
    assert row.status == "completed"
    assert loaded_results == results
