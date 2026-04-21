"""Async SQLAlchemy Engine und Session-Factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings, get_settings

# Module-level singletons — created lazily on first access so that test code
# can replace get_settings() via dependency-override before the engine is built.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        _engine = create_async_engine(
            cfg.database_url,
            # Echo SQL only in non-production environments for debugging.
            echo=cfg.environment != "production",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def _get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(settings),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_async_session(
    settings: Settings | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Async-Generator der eine AsyncSession liefert und am Ende schliesst.

    Wird via FastAPI Depends() genutzt — jeder Request erhält eine eigene
    Session; Rollback bei Exception ist Verantwortung der aufrufenden Schicht.
    """
    factory = _get_session_factory(settings)
    async with factory() as session:
        yield session
