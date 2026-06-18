"""Schema-Tests für ResearchMemoORM (SQLAlchemy-Modell)."""

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM

pytestmark = pytest.mark.unit


class TestTableName:
    def test_tablename(self) -> None:
        assert ResearchMemoORM.__tablename__ == "research_memos"


class TestColumns:
    def test_has_all_16_columns(self) -> None:
        expected = {
            "id",
            "stock_id",
            "model_run_id",
            "language",
            "created_at",
            "one_liner",
            "ranking_interpretation",
            "sweet_spot",
            "sweet_spot_explanation",
            "contradictions",
            "key_strengths",
            "key_risks",
            "confidence",
            "model_version",
            "is_error",
            "user_id",
        }
        actual = {c.name for c in ResearchMemoORM.__table__.columns}
        assert actual == expected

    def test_id_is_uuid_pk(self) -> None:
        col = ResearchMemoORM.__table__.columns["id"]
        assert col.primary_key
        assert isinstance(col.type, UUID)

    def test_created_at_is_timezone_aware(self) -> None:
        col = ResearchMemoORM.__table__.columns["created_at"]
        assert col.type.timezone is True  # type: ignore[attr-defined]
        assert col.nullable is False

    def test_language_default_de(self) -> None:
        col = ResearchMemoORM.__table__.columns["language"]
        assert col.nullable is False
        assert col.default.arg == "de"

    def test_jsonb_columns(self) -> None:
        for name in ("contradictions", "key_strengths", "key_risks"):
            col = ResearchMemoORM.__table__.columns[name]
            assert isinstance(col.type, JSONB), f"{name} should be JSONB"

    def test_sweet_spot_explanation_nullable(self) -> None:
        col = ResearchMemoORM.__table__.columns["sweet_spot_explanation"]
        assert col.nullable is True


class TestForeignKeys:
    def test_stock_id_fk_with_cascade(self) -> None:
        col = ResearchMemoORM.__table__.columns["stock_id"]
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "stocks"
        assert fks[0].ondelete == "CASCADE"

    def test_model_run_id_fk_with_cascade(self) -> None:
        col = ResearchMemoORM.__table__.columns["model_run_id"]
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "ranking_runs"
        assert fks[0].ondelete == "CASCADE"


class TestConstraints:
    def test_unique_constraint_name_and_columns(self) -> None:
        unique = [
            c
            for c in ResearchMemoORM.__table__.constraints  # type: ignore[attr-defined]
            if isinstance(c, UniqueConstraint)
        ]
        assert len(unique) == 1
        assert unique[0].name == "uq_research_memos_stock_run_lang"
        cols = {c.name for c in unique[0].columns}
        assert cols == {"stock_id", "model_run_id", "language"}

    def test_check_constraint_on_confidence(self) -> None:
        checks = [
            c
            for c in ResearchMemoORM.__table__.constraints  # type: ignore[attr-defined]
            if isinstance(c, CheckConstraint)
        ]
        assert len(checks) >= 1
        assert any("confidence" in str(c.sqltext).lower() for c in checks)


class TestIndex:
    def test_index_on_model_run_id(self) -> None:
        indexes = ResearchMemoORM.__table__.indexes  # type: ignore[attr-defined]
        assert any(
            idx.name == "ix_research_memos_model_run_id"
            and {c.name for c in idx.columns} == {"model_run_id"}
            for idx in indexes
        )
