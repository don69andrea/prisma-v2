"""backtest_results.model_run_id → FK auf ranking_runs.id (W3-H-02)

0011 legte `model_run_id` als reines UUID mit Index an — ohne Foreign Key (anders
als research_memos/memo_batch_jobs). Das erlaubt Waisen-Backtests ohne
referenzielle Integrität.

Die FK wird als NOT VALID ergänzt: Integrität wird für alle NEUEN/geänderten
Zeilen erzwungen, ohne bei evtl. bereits vorhandenen Waisen-Zeilen auf einer
Prod-DB fehlzuschlagen (kein destruktives DELETE im Boot-Pfad). Nach einer
bewussten Bereinigung kann die Constraint mit
`ALTER TABLE backtest_results VALIDATE CONSTRAINT fk_backtest_results_model_run_id`
nachvalidiert werden.

Revision ID: 0052
Revises: 0051
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CONSTRAINT = "fk_backtest_results_model_run_id"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE backtest_results ADD CONSTRAINT {_CONSTRAINT} "
        "FOREIGN KEY (model_run_id) REFERENCES ranking_runs (id) "
        "ON DELETE CASCADE NOT VALID"
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "backtest_results", type_="foreignkey")
