"""Unit-Tests für den Boot-Migrations-Guard (C-06, H-12)."""

from __future__ import annotations

import pytest
from alembic import command as alembic_command

from backend.infrastructure.persistence import migration_guard
from backend.infrastructure.persistence.migration_guard import (
    destructive_allowed,
    destructive_in_sources,
    run_boot_migrations,
    scan_destructive,
)

pytestmark = pytest.mark.unit


_BENIGN = """
def upgrade() -> None:
    op.create_table("foo", sa.Column("id", sa.Integer(), primary_key=True))
    op.add_column("foo", sa.Column("bar", sa.String(20)))
    op.create_foreign_key("fk_foo_user", "foo", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.alter_column("foo", "user_id", nullable=False)
"""


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('op.execute("TRUNCATE TABLE alerts CASCADE")', ["TRUNCATE"]),
        ('op.execute("DELETE FROM swiss_rag_chunks")', ["DELETE FROM"]),
        ('op.execute("DROP TABLE users")', ["DROP TABLE"]),
        ('op.execute("ALTER TABLE t DROP COLUMN c")', ["DROP COLUMN"]),
        ('op.drop_table("users")', ["op.drop_table"]),
        ('op.drop_column("t", "c")', ["op.drop_column"]),
    ],
)
def test_scan_detects_destructive(source: str, expected: list[str]) -> None:
    assert scan_destructive(source) == expected


def test_scan_benign_migration_is_clean() -> None:
    assert scan_destructive(_BENIGN) == []


def test_scan_is_case_insensitive_for_sql() -> None:
    assert scan_destructive('op.execute("truncate table x")') == ["TRUNCATE"]


def test_destructive_in_sources_filters_and_reports() -> None:
    sources = [
        ("0051", _BENIGN),
        ("0029", 'op.execute("TRUNCATE TABLE alerts CASCADE")'),
        ("0022", 'op.execute("DELETE FROM swiss_rag_chunks")'),
    ]
    result = destructive_in_sources(sources)
    assert result == [("0029", ["TRUNCATE"]), ("0022", ["DELETE FROM"])]


def test_destructive_in_sources_empty_when_all_benign() -> None:
    assert destructive_in_sources([("0051", _BENIGN), ("0052", _BENIGN)]) == []


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_destructive_allowed_truthy(value: str) -> None:
    assert destructive_allowed({"ALLOW_DESTRUCTIVE_MIGRATIONS": value}) is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "nope"])
def test_destructive_allowed_falsy(value: str) -> None:
    assert destructive_allowed({"ALLOW_DESTRUCTIVE_MIGRATIONS": value}) is False


def test_destructive_allowed_missing_key() -> None:
    assert destructive_allowed({}) is False


# --- run_boot_migrations orchestration (Alembic gemockt, keine DB) ---


_DESTRUCTIVE_PENDING = [("0099", 'op.execute("TRUNCATE TABLE alerts CASCADE")')]


def _patch_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    current: tuple[str, ...],
    pending: list[tuple[str, str]],
) -> list[str]:
    """Verdrahtet den Runner mit Fake-Alembic-Zustand; gibt eine Liste zurück,
    in die jeder command.upgrade-Aufruf 'upgrade' schreibt."""
    upgrades: list[str] = []

    async def _fake_heads(url: str) -> tuple[str, ...]:
        return current

    def _fake_pending(cfg: object, cur: object) -> list[tuple[str, str]]:
        return pending

    def _fake_upgrade(cfg: object, rev: str) -> None:
        upgrades.append(rev)

    monkeypatch.setattr(migration_guard, "_current_heads", _fake_heads)
    monkeypatch.setattr(migration_guard, "_pending_sources", _fake_pending)
    # migration_guard nutzt `from alembic import command`; dasselbe Modulobjekt.
    monkeypatch.setattr(alembic_command, "upgrade", _fake_upgrade)
    return upgrades


def test_run_boot_migrations_blocks_destructive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_MIGRATIONS", raising=False)
    upgrades = _patch_runner(monkeypatch, current=("0050",), pending=_DESTRUCTIVE_PENDING)
    assert run_boot_migrations() == 3
    assert upgrades == []  # nichts angewandt


def test_run_boot_migrations_allows_destructive_with_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_MIGRATIONS", "1")
    upgrades = _patch_runner(monkeypatch, current=("0050",), pending=_DESTRUCTIVE_PENDING)
    assert run_boot_migrations() == 0
    assert upgrades == ["head"]


def test_run_boot_migrations_fresh_db_bootstraps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_MIGRATIONS", raising=False)
    # Frische DB (keine current-Revision) → Guard übersprungen, obwohl pending destruktiv wäre.
    upgrades = _patch_runner(monkeypatch, current=(), pending=_DESTRUCTIVE_PENDING)
    assert run_boot_migrations() == 0
    assert upgrades == ["head"]


def test_run_boot_migrations_runs_when_pending_benign(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_MIGRATIONS", raising=False)
    upgrades = _patch_runner(monkeypatch, current=("0050",), pending=[("0051", _BENIGN)])
    assert run_boot_migrations() == 0
    assert upgrades == ["head"]
