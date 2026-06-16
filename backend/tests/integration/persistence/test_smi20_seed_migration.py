"""Integration-Test fuer die SMI-20-Seed-Migration (0026_seed_smi20_stocks).

Voraussetzung: docker-compose up -d db, alembic upgrade head.

Regressionsschutz fuer den CI-Fehler aus PR #219: SwissStockRepository.get_by_ticker()
filtert auf exchange IS NOT NULL. Die fruehen Seed-Migrationen (0009b, 0012) befuellten
die stocks-Tabelle ausschliesslich mit US-Tickern ohne exchange-Wert; SMI-Ticker
existierten nur nach manuellem Lauf von scripts/seed_smi_universe.py — das passiert in
CI nie. Migration 0025 seedet die SMI-20-Konstituenten direkt mit exchange='XSWX', damit
sie ab `alembic upgrade head` ohne Zusatzschritt auffindbar sind.

Der Test ruft upgrade()/downgrade() aus der Migrationsdatei direkt gegen die Test-Session
auf (statt sich auf den globalen `alembic upgrade head`-Zustand der DB zu verlassen),
weil mehrere bestehende Integrationstests im Repo `TRUNCATE ... stocks CASCADE` als
Cleanup ausfuehren (siehe conftest.py: truncate_research_memos, truncate_universes) und
die stocks-Tabelle dabei nicht wieder befuellen. Dadurch waere ein Test, der nur auf den
Migrationszustand vertraut, von der Ausfuehrungsreihenfolge der Gesamt-Suite abhaengig.
Direkter Aufruf von upgrade()/downgrade() macht den Test deterministisch und unabhaengig.
"""

from __future__ import annotations

import importlib.util
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.swiss_stock import SwissStock
from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
    SQLASwissStockRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

SMI_20_TICKERS = [
    "NESN",
    "NOVN",
    "ROG",
    "ABBN",
    "ZURN",
    "UBSG",
    "UHR",
    "GEBN",
    "GIVN",
    "LONN",
    "SREN",
    "SGKN",
    "SLHN",
    "SCMN",
    "SIKA",
    "HOLN",
    "PGHN",
    "KNIN",
    "CFR",
    "STMN",
]

_MIGRATION_PATH = Path(__file__).parents[3] / "alembic" / "versions" / "0026_seed_smi20_stocks.py"


def _load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "migration_0026_seed_smi20_stocks", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_against_connection(conn, fn: Callable[[], None]) -> None:  # type: ignore[no-untyped-def]
    """Fuehrt `fn` (z.B. `module.upgrade`) so aus, als liefe sie innerhalb einer
    echten Alembic-Migration gegen `conn`.

    Migrationsmodule rufen das globale `alembic.op`-Proxy-Objekt auf, das sich
    normalerweise beim Start von `alembic upgrade` an die aktive `Operations`-Instanz
    bindet. Ausserhalb dieses Flows muss die Bindung manuell ueber die offizielle
    `Operations._install_proxy()`/`_remove_proxy()`-API hergestellt werden (siehe
    alembic.operations.base.Operations / alembic.util.langhelpers.ModuleClsProxy).
    """
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    ctx = MigrationContext.configure(conn)
    operations = Operations(ctx)
    operations._install_proxy()
    try:
        fn()
    finally:
        operations._remove_proxy()


@pytest.fixture
async def smi20_seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    """Wendet exakt die INSERT-Statements der Migration 0025 ueber `op.execute`
    gegen die Test-Connection an und macht sie danach wieder rueckgaengig."""
    module = _load_migration_module()
    async with session_factory() as session:
        sync_conn = await session.connection()
        await sync_conn.run_sync(lambda conn: _run_against_connection(conn, module.upgrade))
        await session.commit()

    yield

    async with session_factory() as session:
        sync_conn = await session.connection()
        await sync_conn.run_sync(lambda conn: _run_against_connection(conn, module.downgrade))
        await session.commit()


@pytest.mark.parametrize("ticker", SMI_20_TICKERS)
async def test_smi20_ticker_is_seeded_with_xswx_exchange(
    session_factory: async_sessionmaker[AsyncSession],
    smi20_seeded: None,
    ticker: str,
) -> None:
    """Jeder SMI-20-Ticker muss nach Anwendung von Migration 0025 ohne manuelles
    Seeding ueber SwissStockRepository.get_by_ticker() auffindbar sein (exchange='XSWX')."""
    async with session_factory() as session:
        repo = SQLASwissStockRepository(session=session)
        stock = await repo.get_by_ticker(ticker)

    assert stock is not None, (
        f"Ticker {ticker!r} fehlt in der stocks-Tabelle oder hat exchange=NULL — "
        "Migration 0026_seed_smi20_stocks wurde nicht angewendet oder ist unvollstaendig."
    )
    assert isinstance(stock, SwissStock)
    assert stock.ticker == ticker
    assert stock.exchange == "XSWX"
    assert stock.currency == "CHF"


async def test_smi20_seed_count_matches_expected_universe_size(
    session_factory: async_sessionmaker[AsyncSession],
    smi20_seeded: None,
) -> None:
    """Es muessen genau die 20 von Migration 0025 geseedeten SMI-Ticker mit
    exchange='XSWX' vorhanden sein (keine Duplikate, keine fehlenden Eintraege)."""
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT ticker FROM stocks WHERE exchange = 'XSWX' ORDER BY ticker")
        )
        seeded_tickers = {row[0] for row in result.fetchall()}

    assert seeded_tickers == set(SMI_20_TICKERS)


async def test_smi20_downgrade_removes_all_seeded_tickers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """downgrade() muss alle 20 SMI-Ticker rueckstandslos entfernen (Symmetrie-Check,
    unabhaengig vom smi20_seeded-Fixture-Teardown)."""
    module = _load_migration_module()

    async with session_factory() as session:
        sync_conn = await session.connection()
        await sync_conn.run_sync(lambda conn: _run_against_connection(conn, module.upgrade))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(text("SELECT count(*) FROM stocks WHERE exchange = 'XSWX'"))
        assert result.scalar_one() == len(SMI_20_TICKERS)

    async with session_factory() as session:
        sync_conn = await session.connection()
        await sync_conn.run_sync(lambda conn: _run_against_connection(conn, module.downgrade))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(text("SELECT count(*) FROM stocks WHERE exchange = 'XSWX'"))
        assert result.scalar_one() == 0
