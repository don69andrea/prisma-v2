"""Integrationstests: geguardeter Migrations-Runner + FK-Verhalten (C-06, W3-H-01).

Läuft gegen die im CI bereits auf head migrierte Test-DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.persistence.migration_guard import run_boot_migrations

pytestmark = pytest.mark.integration


def test_run_boot_migrations_idempotent_at_head() -> None:
    """DB ist bereits auf head → Runner ist No-Op (kein Block, Exit 0)."""
    assert run_boot_migrations() == 0


@pytest.mark.asyncio
async def test_audit_fks_set_null_alerts_cascade(db_session: AsyncSession) -> None:
    """W3-H-01: Audit-/Kosten-/Historie-FKs = SET NULL ('n'); alerts = CASCADE ('c')."""

    async def _confdeltype(conname: str) -> str:
        result = await db_session.execute(
            text("SELECT confdeltype FROM pg_constraint WHERE conname = :name"),
            {"name": conname},
        )
        return str(result.scalar_one())

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
