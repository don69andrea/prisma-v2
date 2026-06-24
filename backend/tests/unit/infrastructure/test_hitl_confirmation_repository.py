"""Unit-Tests für HitlConfirmationRepository — TDD RED phase.

Tests are written BEFORE the implementation exists.
Asserts:
1. insert() returns a UUID for a 'proceed' decision.
2. insert() stores 'abort' decisions correctly.
3. Multiple rows for the same audit_trail_id are allowed (append-only).

Uses async in-memory SQLite via aiosqlite + SQLAlchemy asyncio extension.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.unit

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh in-memory SQLite engine + table creation + async session per test."""
    from backend.infrastructure.persistence.models.hitl_confirmation import HitlConfirmationORM

    engine = create_async_engine(_SQLITE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: HitlConfirmationORM.__table__.create(sync_conn, checkfirst=True)  # type: ignore[attr-defined]
        )

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_insert_persists_decision(session: AsyncSession) -> None:
    """insert() returns a UUID when a 'proceed' decision is stored."""
    from backend.infrastructure.persistence.repositories.hitl_confirmation_repository import (
        HitlConfirmationRepository,
    )

    repo = HitlConfirmationRepository(session=session)
    audit_id = uuid.uuid4()

    result_id = await repo.insert(
        audit_trail_id=audit_id,
        coin="BTC",
        decision="proceed",
    )

    assert isinstance(result_id, uuid.UUID)


@pytest.mark.asyncio
async def test_insert_aborts(session: AsyncSession) -> None:
    """insert() stores an 'abort' decision and returns a UUID."""
    from backend.infrastructure.persistence.models.hitl_confirmation import HitlConfirmationORM
    from backend.infrastructure.persistence.repositories.hitl_confirmation_repository import (
        HitlConfirmationRepository,
    )

    repo = HitlConfirmationRepository(session=session)
    audit_id = uuid.uuid4()

    result_id = await repo.insert(
        audit_trail_id=audit_id,
        coin="ETH",
        decision="abort",
    )

    assert isinstance(result_id, uuid.UUID)

    # Verify the decision was stored correctly
    row = await session.get(HitlConfirmationORM, result_id)
    assert row is not None
    assert row.decision == "abort"
    assert row.coin == "ETH"
    assert row.audit_trail_id == audit_id


@pytest.mark.asyncio
async def test_multiple_confirms_for_same_audit(session: AsyncSession) -> None:
    """Multiple rows for the same audit_trail_id are allowed (append-only)."""
    from backend.infrastructure.persistence.repositories.hitl_confirmation_repository import (
        HitlConfirmationRepository,
    )

    repo = HitlConfirmationRepository(session=session)
    audit_id = uuid.uuid4()

    id1 = await repo.insert(audit_trail_id=audit_id, coin="BTC", decision="proceed")
    id2 = await repo.insert(audit_trail_id=audit_id, coin="BTC", decision="abort")

    # Both inserts succeed and return distinct UUIDs
    assert isinstance(id1, uuid.UUID)
    assert isinstance(id2, uuid.UUID)
    assert id1 != id2
