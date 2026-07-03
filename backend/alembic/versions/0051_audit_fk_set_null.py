"""audit-fk: user-Löschung darf Kosten-/Audit-/Historie nicht vernichten (W3-H-01)

0029 legte auf allen personenbezogenen Tabellen einen ``user_id``-FK mit
``ON DELETE CASCADE`` an. Damit würde das Löschen eines Users Kosten-Log
(``llm_call_log`` = Single-Source-of-Truth des Monatsbudgets), Audit-Log und
Backtest-/Ranking-Historie mitlöschen.

Diese Migration ändert diese FKs auf ``ON DELETE SET NULL`` — die Historie
bleibt erhalten, nur der Owner-Bezug entfällt. ``alerts`` ist ausgenommen:
``alerts.user_id`` ist seit 0050 ``NOT NULL`` (SET NULL wäre unmöglich) und ein
Alert ohne Owner ist wertlos → dort bleibt CASCADE.

Nicht-destruktiv (nur FK-Verhalten), daher vom Boot-Guard nicht blockiert.

Revision ID: 0051
Revises: 0050
Create Date: 2026-07-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Personenbezogene Tabellen aus 0029 OHNE alerts (das bleibt NOT NULL + CASCADE).
_SET_NULL_TABLES = [
    "backtest_results",
    "decision_audit_log",
    "research_memos",
    "ranking_runs",
    "llm_call_log",
    "memo_batch_jobs",
    "investor_profiles",
]


def upgrade() -> None:
    for table in _SET_NULL_TABLES:
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.create_foreign_key(
            f"fk_{table}_user_id",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in _SET_NULL_TABLES:
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.create_foreign_key(
            f"fk_{table}_user_id",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
