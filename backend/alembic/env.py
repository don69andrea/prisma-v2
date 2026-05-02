"""Alembic Environment-Konfiguration — async-Modus mit SQLAlchemy 2.0."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings

# Importiere alle ORM-Modelle damit Alembic ihre Metadaten kennt.
# Neue Modelle hier ergänzen, sonst generiert autogenerate keine Migrationen.
from backend.infrastructure.persistence.base import Base
from backend.infrastructure.persistence.models import llm_call_log, stock  # noqa: F401
from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM  # noqa: F401

# Alembic Config-Objekt, gibt Zugriff auf alembic.ini
config = context.config

# Logging aus alembic.ini konfigurieren
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Liest die DATABASE_URL aus den Anwendungs-Settings (überschreibt alembic.ini)."""
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Offline-Modus: Migrations-SQL wird generiert ohne DB-Verbindung."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Online-Modus: Verbindet sich mit der DB und führt Migrationen async aus."""
    connectable = create_async_engine(get_url(), echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
