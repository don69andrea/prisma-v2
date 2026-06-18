"""DB-Fixture-Setup fuer Integration-Tests (alle Unterverzeichnisse)."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings


@pytest.fixture(autouse=True)
def bypass_jwt_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace JWT auth dependencies in app.py with no-op stubs for all integration tests.

    Tests create their own app instances via create_app(). Because Python resolves
    module-global names at call time, patching before create_app() runs means the
    router-level Depends(...) picks up the stub instead of the real implementation.
    """
    import backend.interfaces.rest.app as _app_mod
    from backend.domain.entities.user import User, UserRole

    _fake = User(
        id=uuid4(),
        email="integration-test-admin@example.com",
        hashed_password="x",
        role=UserRole.admin,
        is_active=True,
    )

    async def _fake_auth() -> User:
        return _fake

    monkeypatch.setattr(_app_mod, "require_current_user", _fake_auth)
    monkeypatch.setattr(_app_mod, "require_admin_role", _fake_auth)


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
    """Async-Session fuer direkte DB-Queries in Tests."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def truncate_embeddings(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    """Per-Test-Cleanup fuer documents+embedding_chunks (CASCADE).

    Verhindert NaN-Similarity-Fehler, die entstehen wenn Persistenz-Tests
    Chunks mit echten Embeddings hinterlassen und RAG-Tests anschliessend
    Zero-Vektor-Mocks gegen nichtleere DB ausfuehren.
    """
    truncate_sql = text("TRUNCATE documents CASCADE")
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()
