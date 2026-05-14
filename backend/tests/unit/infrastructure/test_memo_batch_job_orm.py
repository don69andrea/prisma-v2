"""ORM-Schema-Tests fuer memo_batch_jobs Tabelle."""

import pytest
from sqlalchemy import inspect

from backend.infrastructure.persistence.models.memo_batch_job import (
    MemoBatchJobORM,
)

pytestmark = pytest.mark.unit


def test_table_name() -> None:
    assert MemoBatchJobORM.__tablename__ == "memo_batch_jobs"


def test_columns_present() -> None:
    cols = {c.name for c in inspect(MemoBatchJobORM).columns}
    expected = {
        "id",
        "model_run_id",
        "top_n",
        "language",
        "status",
        "failed_stock_ids",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
    }
    assert expected.issubset(cols)


def test_foreign_key_to_ranking_runs() -> None:
    fks = {
        fk.column.table.name for fk in inspect(MemoBatchJobORM).columns["model_run_id"].foreign_keys
    }
    assert "ranking_runs" in fks


def test_id_is_primary_key() -> None:
    pk_cols = {c.name for c in inspect(MemoBatchJobORM).primary_key}
    assert pk_cols == {"id"}


def test_index_on_model_run_id() -> None:
    indexes = MemoBatchJobORM.__table__.indexes  # type: ignore[attr-defined]
    index_names = {idx.name for idx in indexes}
    assert "ix_memo_batch_jobs_model_run_id" in index_names


def test_check_constraints_named_without_doubling() -> None:
    """Naming-Convention prefix soll Constraint-Namen NICHT verdoppeln
    (Lehre aus PR #54 Foundation Build-Step 5)."""
    constraints = MemoBatchJobORM.__table__.constraints  # type: ignore[attr-defined]
    check_names = {c.name for c in constraints if c.name and c.name.startswith("ck_")}
    assert any("top_n" in n for n in check_names)
    assert any("language" in n for n in check_names)
    assert any("status" in n for n in check_names)
    for name in check_names:
        assert "ck_memo_batch_jobs_ck_memo_batch_jobs" not in name
