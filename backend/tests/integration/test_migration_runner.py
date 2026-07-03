"""Integrationstests: Migrations-Guard-Lesepfad + FK-Verhalten (C-06, W3-H-01).

Läuft gegen die im CI bereits auf head migrierte Test-DB.

Bewusst wird hier NICHT `run_boot_migrations()` (→ `command.upgrade`) aufgerufen:
Alembics `env.py` ruft `fileConfig(alembic.ini)`, was im laufenden Pytest-Prozess
die Logger zurücksetzt und `caplog` anderer Tests bricht. Der echte Upgrade-Pfad
(env.py Advisory-Lock + 0051) wird im CI-Schritt „Run migrations" in einem
separaten Prozess ausgeführt. Hier prüfen wir nur die nebenwirkungsfreien
Lesepfade und das resultierende FK-Verhalten.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.infrastructure.persistence import migration_guard

pytestmark = pytest.mark.integration


def test_pending_is_empty_at_head() -> None:
    """Am head gibt es keine ausstehenden Migrationen → Guard würde nichts blockieren."""
    cfg = migration_guard._build_config()
    heads = asyncio.run(migration_guard._current_heads(get_settings().database_url))
    assert heads, "Test-DB sollte migriert sein (nicht-leere current-Revision)"
    assert migration_guard._pending_sources(cfg, heads) == []


@pytest.mark.asyncio
async def test_audit_fks_set_null_alerts_cascade(db_session: AsyncSession) -> None:
    """W3-H-01: Audit-/Kosten-/Historie-FKs = SET NULL ('n'); alerts = CASCADE ('c')."""

    async def _confdeltype(conname: str) -> str:
        result = await db_session.execute(
            text("SELECT confdeltype FROM pg_constraint WHERE conname = :name"),
            {"name": conname},
        )
        value = result.scalar_one()
        # pg_constraint.confdeltype ist Typ "char" → asyncpg liefert bytes.
        return value.decode() if isinstance(value, bytes | bytearray) else str(value)

    for table in (
        "llm_call_log",
        "decision_audit_log",
        "backtest_results",
        "ranking_runs",
        "research_memos",
        "memo_batch_jobs",
        "investor_profiles",
    ):
        assert await _confdeltype(f"fk_{table}_user_id") == "n", table

    assert await _confdeltype("fk_alerts_user_id") == "c"
