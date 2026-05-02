"""DB-Fixture-Setup für persistence-Integration-Tests."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Frische Engine + Session-Factory pro Test — verhindert Event-Loop-Konflikte
    mit dem Modul-Singleton aus session.py."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=False,
    )
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Async-Session für direkte DB-Queries in Tests."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def truncate_research_memos(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    """Per-Test-Cleanup für research_memos-Tabelle."""
    truncate_sql = text("TRUNCATE research_memos, ranking_runs, universes, stocks CASCADE")
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()
