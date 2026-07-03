"""Guard gegen destruktive Auto-Migrationen im Boot-Pfad (C-06, H-12, W2-H-06).

Ersetzt das blinde ``alembic upgrade head`` in ``backend-start.sh``:

* **Guard:** Ausstehende Migrationen werden auf datenlöschende Operationen
  (``TRUNCATE``, ``DROP TABLE``, ``DELETE FROM``, ``DROP COLUMN``) gescannt.
  Auf einer **bestehenden** DB werden solche Migrationen NICHT automatisch
  angewandt — sie erfordern eine bewusste Freigabe via
  ``ALLOW_DESTRUCTIVE_MIGRATIONS=1`` (ideal: dedizierter One-Off-Job nach
  ``pg_dump``-Backup). Eine **frische/leere** DB (noch keine Alembic-Version)
  wird normal gebootstrappt — dort sind ``TRUNCATE``/``DELETE`` harmlos.
* **Lock:** Die eigentliche Serialisierung paralleler Migrationsläufe passiert
  über ``pg_advisory_xact_lock`` in ``backend/alembic/env.py``.

Die reinen Scan-/Entscheidungsfunktionen sind ohne DB testbar; ``run_boot_migrations``
orchestriert Alembic-Zugriff.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings

_logger = logging.getLogger(__name__)

_ALLOW_ENV = "ALLOW_DESTRUCTIVE_MIGRATIONS"

# Muster für datenlöschende Operationen — rohes SQL (``op.execute("…")``) UND
# Alembic-Op-Aufrufe (``op.drop_table(…)`` / ``op.drop_column(…)``).
_DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("TRUNCATE", re.compile(r"\bTRUNCATE\b", re.IGNORECASE)),
    ("DROP TABLE", re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)),
    ("DELETE FROM", re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)),
    ("DROP COLUMN", re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE)),
    ("op.drop_table", re.compile(r"\.drop_table\s*\(")),
    ("op.drop_column", re.compile(r"\.drop_column\s*\(")),
)


def scan_destructive(source: str) -> list[str]:
    """Gibt die Namen der im Migrations-Source gefundenen destruktiven Operationen zurück."""
    return [name for name, pattern in _DESTRUCTIVE_PATTERNS if pattern.search(source)]


def destructive_in_sources(
    sources: Iterable[tuple[str, str]],
) -> list[tuple[str, list[str]]]:
    """Filtert ``(revision, source)``-Paare auf destruktive Migrationen.

    Rückgabe: ``[(revision, [gefundene_ops])]`` nur für Migrationen mit Treffern.
    """
    result: list[tuple[str, list[str]]] = []
    for revision, source in sources:
        ops = scan_destructive(source)
        if ops:
            result.append((revision, ops))
    return result


def destructive_allowed(env: Mapping[str, str] | None = None) -> bool:
    """True, wenn destruktive Migrationen explizit freigegeben sind."""
    raw = (env if env is not None else os.environ).get(_ALLOW_ENV, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_config() -> Config:
    # CWD-relativ auflösen — identisch zum `alembic`-CLI (Container-WORKDIR /app
    # und CI-Repo-Root enthalten beide alembic.ini + backend/alembic).
    return Config("alembic.ini")


async def _current_heads(url: str) -> tuple[str, ...]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            heads = await conn.run_sync(
                lambda sync_conn: MigrationContext.configure(sync_conn).get_current_heads()
            )
        return tuple(heads)
    finally:
        await engine.dispose()


def _pending_sources(cfg: Config, current: Sequence[str]) -> list[tuple[str, str]]:
    """Liest Source-Text aller ausstehenden Migrationen (head … exkl. current)."""
    script = ScriptDirectory.from_config(cfg)
    out: list[tuple[str, str]] = []
    for rev in script.iterate_revisions("heads", tuple(current)):
        out.append((rev.revision, Path(rev.path).read_text(encoding="utf-8")))
    return out


def run_boot_migrations() -> int:
    """Boot-Migrations-Runner mit Guard. Exit-Code: 0 = ok, 3 = blockiert."""
    url = get_settings().database_url
    cfg = _build_config()

    current = asyncio.run(_current_heads(url))
    if not current:
        _logger.info("Frische DB (keine Alembic-Version) — Bootstrap: alle Migrationen anwenden.")
        command.upgrade(cfg, "head")
        return 0

    pending = _pending_sources(cfg, current)
    destructive = destructive_in_sources(pending)
    if destructive and not destructive_allowed():
        detail = "; ".join(f"{rev} ({', '.join(ops)})" for rev, ops in destructive)
        _logger.error(
            "BLOCKIERT: ausstehende destruktive Migration(en) — %s. "
            "Auto-Migration abgebrochen (keine Daten verändert). "
            "Zum bewussten Anwenden (nach pg_dump-Backup): %s=1 setzen und erneut ausführen.",
            detail,
            _ALLOW_ENV,
        )
        return 3

    command.upgrade(cfg, "head")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(run_boot_migrations())
