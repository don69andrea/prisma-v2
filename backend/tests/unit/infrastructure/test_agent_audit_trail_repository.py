"""Unit-Tests für AgentAuditTrailRepository — append-only contract (D-02).

TDD RED phase: these tests are written BEFORE the repository exists.
They assert:
1. insert() returns the row's UUID.
2. Two insert() calls with the same coin/asof → 2 distinct rows (append-only).
3. Repository exposes NO update(), delete(), or save() method.

Uses async in-memory SQLite via aiosqlite + SQLAlchemy asyncio extension.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.infrastructure.persistence.base import Base
from backend.infrastructure.persistence.models.agent_audit_trail import AgentAuditTrailORM
from backend.infrastructure.persistence.repositories.agent_audit_trail_repository import (
    AgentAuditTrailRepository,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# In-memory SQLite fixture (unit-test scope — no real DB required)
# ---------------------------------------------------------------------------

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh in-memory SQLite engine + table creation + async session per test.

    SQLite does not support gen_random_uuid() or now() server_defaults, but
    the ORM model supplies Python-side defaults (uuid.uuid4, datetime.now(UTC))
    so all unit tests work without any PostgreSQL.
    """
    engine = create_async_engine(_SQLITE_URL, echo=False)

    async with engine.begin() as conn:
        # Create only the agent_audit_trail table — avoids pulling in full
        # metadata for unrelated tables that have FK dependencies.
        await conn.run_sync(
            lambda sync_conn: AgentAuditTrailORM.__table__.create(sync_conn, checkfirst=True)
        )

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as sess:
        yield sess

    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_AGENT_RUN: dict = {
    "tech_view": {"stance": "BULLISH", "confidence": 0.8},
    "onchain_view": {"valuation": "CHEAP", "network_health": "STRONG"},
    "senti_view": {"score": 0.3, "regime": "GREED"},
    "macro_regime": {"regime": "RISK_ON", "confidence": 0.7},
    "bull_case": {"thesis": "Strong momentum"},
    "bear_case": {"thesis": "High valuation risk"},
    "risk_verdict": {"approve": True, "max_size": 1.0},
    "trade_signal": {"action": "BUY", "size_factor": 0.8, "confidence": 0.75},
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_insert_returns_uuid(session: AsyncSession) -> None:
    """insert() must return a uuid.UUID instance (the persisted row's PK)."""
    repo = AgentAuditTrailRepository(session)
    result = await repo.insert(
        coin="BTC",
        asof=date(2026, 6, 21),
        agent_run=_SAMPLE_AGENT_RUN,
    )
    assert isinstance(result, uuid.UUID), f"Expected uuid.UUID, got {type(result)}"


async def test_insert_returns_real_db_id(session: AsyncSession) -> None:
    """The returned UUID must match the row that was actually written to the DB."""
    repo = AgentAuditTrailRepository(session)
    returned_id = await repo.insert(
        coin="ETH",
        asof=date(2026, 6, 21),
        agent_run=_SAMPLE_AGENT_RUN,
    )

    # Verify row exists in DB with the returned id
    stmt = sa.select(AgentAuditTrailORM).where(AgentAuditTrailORM.id == returned_id)
    row = (await session.execute(stmt)).scalar_one_or_none()

    assert row is not None, "Row not found in DB after insert()"
    assert row.id == returned_id
    assert row.coin == "ETH"


async def test_append_only_two_inserts_create_two_rows(session: AsyncSession) -> None:
    """D-02 append-only contract: two insert() calls → two distinct rows.

    Identical coin/asof MUST produce two rows (not an upsert/overwrite).
    Row count must be exactly 2 and the returned UUIDs must differ.
    """
    repo = AgentAuditTrailRepository(session)
    coin = "BTC"
    asof = date(2026, 6, 21)

    id_1 = await repo.insert(coin=coin, asof=asof, agent_run=_SAMPLE_AGENT_RUN)
    id_2 = await repo.insert(coin=coin, asof=asof, agent_run=_SAMPLE_AGENT_RUN)

    # Two distinct UUIDs
    assert id_1 != id_2, "Two insert() calls must produce two distinct UUIDs"

    # Exactly two rows in the table
    count_stmt = sa.select(sa.func.count()).select_from(AgentAuditTrailORM)
    row_count = (await session.execute(count_stmt)).scalar_one()
    assert row_count == 2, f"Expected 2 rows after two inserts, got {row_count}"


async def test_insert_stores_jsonb_agent_run(session: AsyncSession) -> None:
    """agent_run JSONB column must store and retrieve arbitrary dict correctly."""
    repo = AgentAuditTrailRepository(session)
    custom_run = {
        "bull_case": "Strong demand",
        "bear_case": "Regulatory headwinds",
        "risk_verdict": {"approve": False, "max_size": 0.0},
        "reasoning": "Caution warranted given macro RISK_OFF regime.",
    }
    returned_id = await repo.insert(
        coin="SOL",
        asof=date(2026, 6, 21),
        agent_run=custom_run,
    )

    stmt = sa.select(AgentAuditTrailORM).where(AgentAuditTrailORM.id == returned_id)
    row = (await session.execute(stmt)).scalar_one()

    assert row.agent_run == custom_run, "agent_run JSONB did not round-trip correctly"


def test_repository_has_no_update_method() -> None:
    """Immutability contract: AgentAuditTrailRepository must NOT expose update()."""
    assert not hasattr(AgentAuditTrailRepository, "update"), (
        "AgentAuditTrailRepository must NOT have an update() method (D-02)"
    )


def test_repository_has_no_delete_method() -> None:
    """Immutability contract: AgentAuditTrailRepository must NOT expose delete()."""
    assert not hasattr(AgentAuditTrailRepository, "delete"), (
        "AgentAuditTrailRepository must NOT have a delete() method (D-02)"
    )


def test_repository_has_no_save_overwrite_method() -> None:
    """Immutability contract: AgentAuditTrailRepository must NOT expose save().

    save() commonly implies upsert/overwrite semantics — forbidden here.
    """
    assert not hasattr(AgentAuditTrailRepository, "save"), (
        "AgentAuditTrailRepository must NOT have a save() method (D-02)"
    )


def test_repository_exposes_insert_method() -> None:
    """Repository must expose exactly one write method: insert()."""
    assert hasattr(AgentAuditTrailRepository, "insert"), (
        "AgentAuditTrailRepository must expose insert() method"
    )
