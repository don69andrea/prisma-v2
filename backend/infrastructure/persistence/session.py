"""Async SQLAlchemy Engine und Session-Factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from backend.config import Settings, get_settings

# Module-level singletons — created lazily on first access so that test code
# can replace get_settings() via dependency-override before the engine is built.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        if cfg.environment == "test":
            # NullPool verhindert Connection-Reuse über pytest-function-Event-Loops.
            # Jede DB-Operation bekommt eine frische Connection → kein "different loop" Error.
            _engine = create_async_engine(
                cfg.database_url,
                echo=True,
                poolclass=NullPool,
            )
        else:
            _engine = create_async_engine(
                cfg.database_url,
                echo=cfg.environment != "production",
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
    return _engine


def get_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Liefert die Module-singleton Session-Factory.

    Wird benutzt von Repos, die eigene Sessions pro Operation öffnen müssen
    (z.B. Audit-Log-Inserts, die nicht an Request-Sessions gekoppelt sein
    dürfen, um nicht laufende Business-Operationen mit-zu-committen).
    """
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
    Session. Bei erfolgreichem Request-Handler-Return wird committet,
    bei Exception rollback'd.
    """
    factory = get_session_factory(settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
