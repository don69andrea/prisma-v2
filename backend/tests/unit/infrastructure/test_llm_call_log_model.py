"""Unit-Tests für das LLMCallLog SQLAlchemy-Modell.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §3 + §11.3.

Testet die Schema-Struktur (Spalten, Typen, Index) ohne echte DB-Verbindung —
fängt Drift zwischen Modell und Spec.
"""

import pytest

from backend.infrastructure.persistence.models.llm_call_log import LLMCallLogORM

pytestmark = pytest.mark.unit


class TestLLMCallLogTable:
    def test_tablename_is_llm_call_log(self) -> None:
        assert LLMCallLogORM.__tablename__ == "llm_call_log"

    def test_has_all_required_columns(self) -> None:
        columns = {col.name for col in LLMCallLogORM.__table__.columns}
        expected = {
            "id",
            "created_at",
            "provider",
            "model",
            "feature",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "request_id",
            "user_id",
        }
        assert columns == expected

    def test_id_is_primary_key(self) -> None:
        id_col = LLMCallLogORM.__table__.c.id
        assert id_col.primary_key is True

    def test_created_at_is_timezone_aware(self) -> None:
        col = LLMCallLogORM.__table__.c.created_at
        # SQLAlchemy DateTime exposes `timezone` at runtime; mypy doesn't see
        # the concrete type because __table__.c returns generic Column[Any].
        assert col.type.timezone is True  # type: ignore[attr-defined]

    def test_cost_usd_uses_numeric_with_correct_precision(self) -> None:
        # NUMERIC(10, 6) per Spec §3 — Decimal, nie Float
        col = LLMCallLogORM.__table__.c.cost_usd
        assert col.type.precision == 10  # type: ignore[attr-defined]
        assert col.type.scale == 6  # type: ignore[attr-defined]

    def test_required_fields_are_not_nullable(self) -> None:
        for required in (
            "provider",
            "model",
            "feature",
            "input_tokens",
            "output_tokens",
            "cost_usd",
        ):
            col = LLMCallLogORM.__table__.c[required]
            assert col.nullable is False, f"{required} should be NOT NULL"

    def test_request_id_is_nullable(self) -> None:
        col = LLMCallLogORM.__table__.c.request_id
        assert col.nullable is True

    def test_has_index_on_created_at(self) -> None:
        # Cap-Check-Query filtert nach created_at — ohne Index wird das langsam
        index_columns = [
            tuple(c.name for c in idx.columns)
            for idx in LLMCallLogORM.__table__.indexes  # type: ignore[attr-defined]
        ]
        assert ("created_at",) in index_columns
