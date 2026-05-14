"""Integration-Tests für SQLAUniverseRepository gegen Live-Postgres.

Fokus: doppelter save()-Aufruf in derselben Session (Identity-Map-Bug-Regression
analog zu RankingRunRepository).
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import backend.infrastructure.persistence.session as session_module
from backend.domain.entities.universe import Universe
from backend.infrastructure.persistence.repositories.universe_repository import (
    SQLAUniverseRepository,
)

pytestmark = [pytest.mark.integration]


@pytest_asyncio.fixture
async def truncate_universes(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    truncate_sql = text("TRUNCATE universes, stocks CASCADE")
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()


def _new_universe(name: str = "Test-Universe") -> Universe:
    return Universe(
        id=uuid.uuid4(),
        name=name,
        region="US",
        tickers=("AAPL", "MSFT"),
    )


async def test_save_twice_updates_instead_of_insert(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_universes: None,
) -> None:
    """Regression: zweiter save() mit gleicher ID muss UPDATE machen, nicht INSERT.

    Bug: bei autoflush=False findet session.get() die noch-pending Row vom ersten
    save() nicht → zweiter save() trifft den add-Pfad → INSERT mit Duplicate-PK.
    """
    universe = _new_universe()

    async with session_factory() as session:
        repo = SQLAUniverseRepository(session)
        await repo.save(universe)

        renamed = universe.model_copy(update={"name": "Renamed-Universe"})
        await repo.save(renamed)

        await session.commit()

    # Verifikation in separater Session
    async with session_factory() as session:
        row = await SQLAUniverseRepository(session).get(universe.id)
        assert row is not None
        assert row.name == "Renamed-Universe"


async def test_get_async_session_rolls_back_on_handler_exception(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_universes: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: Exception aus dem yielded-Block → rollback, kein silent commit.

    Schützt die try/yield/commit/except/rollback-Semantik in get_async_session()
    — wenn jemand try/except aufweicht oder einen Wrapper-Generator zwischenschiebt
    der die Exception schluckt, landen Teil-Writes unrollback'd in der DB.
    """
    # get_async_session() nutzt eine Modul-Singleton-Factory. Damit der Test
    # die fresh-pro-Test-Factory aus conftest nutzt (Event-Loop-Affinität),
    # patchen wir den Factory-Getter — die try/commit/except/rollback-Logik
    # in get_async_session selbst bleibt unverändert unter Test.
    monkeypatch.setattr(
        session_module, "get_session_factory", lambda settings=None: session_factory
    )

    universe = _new_universe(name="Rollback-Probe")

    gen = session_module.get_async_session()
    session = await anext(gen)
    await SQLAUniverseRepository(session).save(universe)

    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))

    # Verifikation: row darf NICHT persistiert sein
    async with session_factory() as verify_session:
        row = await SQLAUniverseRepository(verify_session).get(universe.id)
    assert row is None
