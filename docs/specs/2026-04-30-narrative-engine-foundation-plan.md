# Narrative-Engine Foundation — Implementation Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** Foundation für die Narrative-Engine implementieren (Issue #17, PR #1) — Pydantic-Schema, Domain-Entity, ORM, Migration, Repository-Port + SQLA-Adapter mit Tests.

**Architecture:** 7 TDD-Tasks, jede ein eigener Commit, alle in einem PR auf `feat/017-narrative-engine`. Hex-Architektur strikt. Pydantic v2 überall. async SQLAlchemy. Tests in `tests/unit/` (Schema/Entity/ORM) + `tests/integration/persistence/` (Repository-Roundtrip gegen Postgres).

**Tech Stack:** Python 3.12, Pydantic 2.6+, SQLAlchemy 2.0 (async), asyncpg, alembic 1.13, pytest 8 + pytest-asyncio (asyncio_mode=auto), uuid, datetime UTC.

**Spec-Referenz:** `docs/specs/2026-04-30-narrative-engine-foundation.md`

---

## File Structure

| Datei | Verantwortung | Task |
|-------|---------------|------|
| `backend/domain/entities/research_memo.py` | `ContradictionItem` (Value-Object) + `ResearchMemo` (Entity) | 1, 3 |
| `backend/domain/schemas/__init__.py` | Modul-Init | 2 |
| `backend/domain/schemas/research_memo_schema.py` | `ResearchMemoSchema` (LLM-Vertrag) | 2 |
| `backend/domain/repositories/research_memo_repository.py` | `ResearchMemoRepository` ABC (Port) | 6 |
| `backend/infrastructure/persistence/models/research_memo.py` | `ResearchMemoORM` SQLAlchemy-Modell | 4 |
| `backend/infrastructure/persistence/repositories/research_memo_repository.py` | `SQLAResearchMemoRepository` Adapter | 7 |
| `backend/alembic/versions/0005_create_research_memos.py` | Migration | 5 |
| `backend/alembic/env.py` | Import-Statement für Auto-Discovery | 5 |
| `backend/tests/unit/domain/schemas/__init__.py` + `test_research_memo_schema.py` | Schema-Tests | 1, 2 |
| `backend/tests/unit/domain/entities/__init__.py` + `test_research_memo.py` | Entity-Tests | 1, 3 |
| `backend/tests/unit/infrastructure/test_research_memo_orm.py` | ORM-Schema-Tests | 4 |
| `backend/tests/integration/persistence/__init__.py` + `test_research_memo_repository.py` | Repository-Roundtrip-Tests | 7 |

---

## Task 1: ContradictionItem (Value-Object)

**Files:**
- Create: `backend/domain/entities/research_memo.py`
- Create: `backend/tests/unit/domain/entities/__init__.py`
- Create: `backend/tests/unit/domain/entities/test_research_memo.py`

- [ ] **Step 1: Write failing tests for `ContradictionItem`**

```python
# backend/tests/unit/domain/entities/test_research_memo.py
import pytest
from pydantic import ValidationError

from backend.domain.entities.research_memo import ContradictionItem


pytestmark = pytest.mark.unit


class TestContradictionItem:
    def test_valid_construct(self) -> None:
        item = ContradictionItem(
            model_a="Quality Classic",
            model_b="Diversification",
            description="Top in Quality, schwach in Risiko-Diversifikation.",
        )
        assert item.model_a == "Quality Classic"

    def test_is_frozen(self) -> None:
        item = ContradictionItem(model_a="A", model_b="B", description="x" * 50)
        with pytest.raises(ValidationError):
            item.model_a = "C"  # type: ignore[misc]

    def test_description_max_length_200(self) -> None:
        with pytest.raises(ValidationError):
            ContradictionItem(model_a="A", model_b="B", description="x" * 201)

    def test_model_a_min_length_1(self) -> None:
        with pytest.raises(ValidationError):
            ContradictionItem(model_a="", model_b="B", description="x" * 50)

    def test_model_a_max_length_64(self) -> None:
        with pytest.raises(ValidationError):
            ContradictionItem(model_a="x" * 65, model_b="B", description="x" * 50)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest backend/tests/unit/domain/entities/test_research_memo.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domain.entities.research_memo'`

- [ ] **Step 3: Implement `ContradictionItem`**

```python
# backend/domain/entities/research_memo.py
from pydantic import BaseModel, ConfigDict, Field


class ContradictionItem(BaseModel):
    """Modell-zu-Modell-Widerspruch.

    Lebt hier (nicht im Schema-File), weil sowohl ResearchMemoSchema
    als auch ResearchMemo ihn nutzen.
    """

    model_config = ConfigDict(frozen=True)

    model_a: str = Field(..., min_length=1, max_length=64)
    model_b: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., max_length=200)
```

Plus leere `backend/tests/unit/domain/entities/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest backend/tests/unit/domain/entities/test_research_memo.py -v
```
Expected: 5 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend python -m mypy backend/domain/entities/research_memo.py backend/tests/unit/domain/entities/test_research_memo.py
docker compose exec backend python -m ruff check backend/domain/entities/research_memo.py backend/tests/unit/domain/entities/test_research_memo.py
docker compose exec backend python -m ruff format --check backend/domain/entities/research_memo.py backend/tests/unit/domain/entities/test_research_memo.py
```
Expected: alle 3 grün.

```bash
git add backend/domain/entities/research_memo.py backend/tests/unit/domain/entities/__init__.py backend/tests/unit/domain/entities/test_research_memo.py
git commit -m "feat(domain): ContradictionItem Value-Object für ResearchMemo (#17, build-step 1/7)

Frozen Pydantic-Klasse, geteilt zwischen ResearchMemoSchema (LLM-Output)
und ResearchMemo (Entity). 5 Unit-Tests in TDD-Reihenfolge geschrieben
(RED→GREEN): valid construct, frozen, description-max-length-200,
model_a-min-length-1, model_a-max-length-64.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: ResearchMemoSchema (LLM-Output-Vertrag)

**Files:**
- Create: `backend/domain/schemas/__init__.py`
- Create: `backend/domain/schemas/research_memo_schema.py`
- Create: `backend/tests/unit/domain/schemas/__init__.py`
- Create: `backend/tests/unit/domain/schemas/test_research_memo_schema.py`

- [ ] **Step 1: Write failing tests for `ResearchMemoSchema`**

```python
# backend/tests/unit/domain/schemas/test_research_memo_schema.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.domain.entities.research_memo import ContradictionItem
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema


pytestmark = pytest.mark.unit


def _valid_payload() -> dict:
    return {
        "ticker": "NESN",
        "total_rank": 12,
        "one_liner": "Solides Quality-Profil mit moderatem Trend.",
        "ranking_interpretation": "x" * 200,
        "sweet_spot": False,
        "sweet_spot_explanation": None,
        "contradictions": [],
        "key_strengths": ["Stabilität", "Dividende"],
        "key_risks": ["FX-Exposure"],
        "confidence": "medium",
        "generated_at": datetime.now(UTC),
        "model_version": "claude-sonnet-4-6@20260101",
    }


class TestValidConstruct:
    def test_minimal_valid(self) -> None:
        schema = ResearchMemoSchema(**_valid_payload())
        assert schema.ticker == "NESN"
        assert schema.confidence == "medium"

    def test_with_contradictions(self) -> None:
        payload = _valid_payload()
        payload["contradictions"] = [
            ContradictionItem(model_a="Quality", model_b="Trend", description="x" * 50),
        ]
        schema = ResearchMemoSchema(**payload)
        assert len(schema.contradictions) == 1


class TestStringLengthConstraints:
    def test_one_liner_too_short(self) -> None:
        payload = _valid_payload()
        payload["one_liner"] = "x" * 9  # min=10
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_one_liner_too_long(self) -> None:
        payload = _valid_payload()
        payload["one_liner"] = "x" * 151
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_ranking_interpretation_too_short(self) -> None:
        payload = _valid_payload()
        payload["ranking_interpretation"] = "x" * 99  # min=100
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_sweet_spot_explanation_too_long(self) -> None:
        payload = _valid_payload()
        payload["sweet_spot_explanation"] = "x" * 301
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)


class TestListConstraints:
    def test_contradictions_max_3(self) -> None:
        payload = _valid_payload()
        payload["contradictions"] = [
            ContradictionItem(model_a=f"M{i}", model_b="X", description="x" * 50)
            for i in range(4)
        ]
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_key_strengths_min_1(self) -> None:
        payload = _valid_payload()
        payload["key_strengths"] = []
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_key_strengths_max_5(self) -> None:
        payload = _valid_payload()
        payload["key_strengths"] = ["a", "b", "c", "d", "e", "f"]
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)


class TestEnumLikeFields:
    def test_confidence_must_be_valid_literal(self) -> None:
        payload = _valid_payload()
        payload["confidence"] = "very_high"
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_total_rank_must_be_positive(self) -> None:
        payload = _valid_payload()
        payload["total_rank"] = 0
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest backend/tests/unit/domain/schemas/test_research_memo_schema.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domain.schemas'`

- [ ] **Step 3: Implement `ResearchMemoSchema`**

Create empty `backend/domain/schemas/__init__.py` and `backend/tests/unit/domain/schemas/__init__.py`.

```python
# backend/domain/schemas/research_memo_schema.py
"""Pydantic-Schemas für externe Verträge (LLM-Output etc.)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.domain.entities.research_memo import ContradictionItem


class ResearchMemoSchema(BaseModel):
    """LLM-Output-Vertrag — was wir von Claude erwarten.

    Master-Spec §4 wortgetreu. Wird im Service zu ResearchMemo (Entity)
    gemappt — Mapping kommt in Folge-PR.
    """

    ticker: str = Field(..., min_length=1, max_length=10)
    total_rank: int = Field(..., ge=1)

    one_liner: str = Field(..., min_length=10, max_length=150)
    ranking_interpretation: str = Field(..., min_length=100, max_length=600)
    sweet_spot: bool
    sweet_spot_explanation: str | None = Field(None, max_length=300)
    contradictions: list[ContradictionItem] = Field(default_factory=list, max_length=3)
    key_strengths: list[str] = Field(..., min_length=1, max_length=5)
    key_risks: list[str] = Field(..., min_length=1, max_length=5)
    confidence: Literal["low", "medium", "high"]

    generated_at: datetime
    model_version: str = Field(..., min_length=1, max_length=64)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest backend/tests/unit/domain/schemas/test_research_memo_schema.py -v
```
Expected: 11 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend python -m mypy backend/domain/schemas/ backend/tests/unit/domain/schemas/
docker compose exec backend python -m ruff check backend/domain/schemas/ backend/tests/unit/domain/schemas/
docker compose exec backend python -m ruff format --check backend/domain/schemas/ backend/tests/unit/domain/schemas/
```

```bash
git add backend/domain/schemas/__init__.py backend/domain/schemas/research_memo_schema.py backend/tests/unit/domain/schemas/__init__.py backend/tests/unit/domain/schemas/test_research_memo_schema.py
git commit -m "feat(domain): ResearchMemoSchema — LLM-Output-Vertrag (#17, build-step 2/7)

Pydantic-Schema gemäss Master-Spec §4 mit allen Validation-Constraints
(min_length, max_length, max_length auf Listen, Literal-Enum für confidence,
ge=1 für total_rank). 11 Unit-Tests RED→GREEN: valid construct (2),
String-Constraints (4), List-Constraints (3), Enum-likes (2).

Lebt in neuem Verzeichnis backend/domain/schemas/ — Pydantic-DTOs für
externe Verträge (LLM, später ggf. weitere). Trennung von domain/entities/
ist bewusst: Schema-Vertrag co-evolviert mit Prompts, Entity nicht.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: ResearchMemo Entity

**Files:**
- Modify: `backend/domain/entities/research_memo.py` (add `ResearchMemo` class)
- Modify: `backend/tests/unit/domain/entities/test_research_memo.py` (add test class)

- [ ] **Step 1: Write failing tests for `ResearchMemo` Entity**

Append to `backend/tests/unit/domain/entities/test_research_memo.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from backend.domain.entities.research_memo import ResearchMemo


def _valid_entity_payload() -> dict:
    return {
        "id": uuid4(),
        "stock_id": uuid4(),
        "model_run_id": uuid4(),
        "language": "de",
        "created_at": datetime.now(UTC),
        "one_liner": "kurz aber valide",
        "ranking_interpretation": "x" * 200,
        "sweet_spot": False,
        "sweet_spot_explanation": None,
        "contradictions": [],
        "key_strengths": ["Stabilität"],
        "key_risks": ["FX"],
        "confidence": "medium",
        "model_version": "claude-sonnet-4-6@20260101",
    }


class TestResearchMemoEntity:
    def test_valid_construct(self) -> None:
        memo = ResearchMemo(**_valid_entity_payload())
        assert memo.language == "de"

    def test_language_default_is_de(self) -> None:
        payload = _valid_entity_payload()
        del payload["language"]
        memo = ResearchMemo(**payload)
        assert memo.language == "de"

    def test_language_accepts_en(self) -> None:
        payload = _valid_entity_payload()
        payload["language"] = "en"
        memo = ResearchMemo(**payload)
        assert memo.language == "en"

    def test_is_frozen(self) -> None:
        memo = ResearchMemo(**_valid_entity_payload())
        with pytest.raises(ValidationError):
            memo.one_liner = "neuer text"  # type: ignore[misc]

    def test_entity_accepts_short_one_liner_schema_would_reject(self) -> None:
        """Constraint-Asymmetrie zum Schema: Entity erlaubt kurze Strings,
        die das LLM-Schema zurückweisen würde. Bewusst (Spec §3.3)."""
        payload = _valid_entity_payload()
        payload["one_liner"] = "kurz"  # 4 Zeichen, im Schema min=10
        memo = ResearchMemo(**payload)
        assert memo.one_liner == "kurz"

    def test_one_liner_max_length_still_enforced(self) -> None:
        payload = _valid_entity_payload()
        payload["one_liner"] = "x" * 151
        with pytest.raises(ValidationError):
            ResearchMemo(**payload)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest backend/tests/unit/domain/entities/test_research_memo.py::TestResearchMemoEntity -v
```
Expected: FAIL with `ImportError: cannot import name 'ResearchMemo'`

- [ ] **Step 3: Implement `ResearchMemo` Entity (append to existing file)**

Append to `backend/domain/entities/research_memo.py`:

```python
from datetime import datetime
from typing import Literal
from uuid import UUID


class ResearchMemo(BaseModel):
    """Persistierte Domain-Entity für ein Research-Memo.

    Constraints sind die DB-CHECK/Length-Constraints. Strengere
    LLM-Output-Validation lebt im ResearchMemoSchema (siehe schemas/).
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    stock_id: UUID
    model_run_id: UUID
    language: Literal["de", "en"] = "de"
    created_at: datetime

    one_liner: str = Field(..., max_length=150)
    ranking_interpretation: str = Field(..., max_length=600)
    sweet_spot: bool
    sweet_spot_explanation: str | None = Field(None, max_length=300)
    contradictions: list[ContradictionItem] = Field(default_factory=list)
    key_strengths: list[str]
    key_risks: list[str]
    confidence: Literal["low", "medium", "high"]
    model_version: str = Field(..., max_length=64)
```

Add `from datetime import datetime`, `from typing import Literal`, `from uuid import UUID` to existing imports.

- [ ] **Step 4: Run all entity tests + verify pass**

```bash
docker compose exec backend pytest backend/tests/unit/domain/entities/test_research_memo.py -v
```
Expected: 11 passed (5 ContradictionItem + 6 ResearchMemo)

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend python -m mypy backend/domain/ backend/tests/unit/domain/
docker compose exec backend python -m ruff check backend/domain/ backend/tests/unit/domain/
docker compose exec backend python -m ruff format --check backend/domain/ backend/tests/unit/domain/
```

```bash
git add backend/domain/entities/research_memo.py backend/tests/unit/domain/entities/test_research_memo.py
git commit -m "feat(domain): ResearchMemo Entity mit Constraint-Asymmetrie zu Schema (#17, build-step 3/7)

Pydantic-Entity mit DB-Feldern (id, stock_id, model_run_id, language,
created_at) plus alle Schema-Felder. Frozen=True (Defensive-Coding).
Constraints sind nur DB-Length-Constraints (max_length); strengere
LLM-Validation (min_length etc.) bleibt im Schema (Spec §3.3).

6 Unit-Tests RED→GREEN: valid construct, language default 'de', en
accepted, frozen behavior, constraint-asymmetry test (kurzer one_liner
in Entity ok, im Schema nicht), max_length still enforced.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: ResearchMemoORM (SQLAlchemy-Modell)

**Files:**
- Create: `backend/infrastructure/persistence/models/research_memo.py`
- Create: `backend/tests/unit/infrastructure/test_research_memo_orm.py`

- [ ] **Step 1: Write failing tests for ORM-Schema**

```python
# backend/tests/unit/infrastructure/test_research_memo_orm.py
import pytest
from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM


pytestmark = pytest.mark.unit


class TestTableName:
    def test_tablename(self) -> None:
        assert ResearchMemoORM.__tablename__ == "research_memos"


class TestColumns:
    def test_has_all_14_columns(self) -> None:
        expected = {
            "id", "stock_id", "model_run_id", "language", "created_at",
            "one_liner", "ranking_interpretation", "sweet_spot",
            "sweet_spot_explanation", "contradictions",
            "key_strengths", "key_risks", "confidence", "model_version",
        }
        actual = {c.name for c in ResearchMemoORM.__table__.columns}
        assert actual == expected

    def test_id_is_uuid_pk(self) -> None:
        col = ResearchMemoORM.__table__.columns["id"]
        assert col.primary_key
        assert isinstance(col.type, UUID)

    def test_created_at_is_timezone_aware(self) -> None:
        col = ResearchMemoORM.__table__.columns["created_at"]
        assert col.type.timezone is True
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
            c for c in ResearchMemoORM.__table__.constraints
            if isinstance(c, UniqueConstraint)
        ]
        assert len(unique) == 1
        assert unique[0].name == "uq_research_memos_stock_run_lang"
        cols = {c.name for c in unique[0].columns}
        assert cols == {"stock_id", "model_run_id", "language"}

    def test_check_constraint_on_confidence(self) -> None:
        checks = [
            c for c in ResearchMemoORM.__table__.constraints
            if isinstance(c, CheckConstraint)
        ]
        assert len(checks) >= 1
        assert any("confidence" in str(c.sqltext).lower() for c in checks)


class TestIndex:
    def test_index_on_model_run_id(self) -> None:
        indexes = ResearchMemoORM.__table__.indexes
        assert any(
            idx.name == "ix_research_memos_model_run_id"
            and {c.name for c in idx.columns} == {"model_run_id"}
            for idx in indexes
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest backend/tests/unit/infrastructure/test_research_memo_orm.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `ResearchMemoORM`**

```python
# backend/infrastructure/persistence/models/research_memo.py
"""SQLAlchemy ORM-Modell für research_memos (Spec §4)."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.models.base import Base


class ResearchMemoORM(Base):
    __tablename__ = "research_memos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ranking_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="de",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    one_liner: Mapped[str] = mapped_column(String(150), nullable=False)
    ranking_interpretation: Mapped[str] = mapped_column(String(600), nullable=False)
    sweet_spot: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sweet_spot_explanation: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )
    contradictions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    key_strengths: Mapped[list] = mapped_column(JSONB, nullable=False)
    key_risks: Mapped[list] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "stock_id", "model_run_id", "language",
            name="uq_research_memos_stock_run_lang",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="confidence",
        ),
        Index("ix_research_memos_model_run_id", "model_run_id"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest backend/tests/unit/infrastructure/test_research_memo_orm.py -v
```
Expected: 12 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend python -m mypy backend/infrastructure/persistence/models/research_memo.py backend/tests/unit/infrastructure/test_research_memo_orm.py
docker compose exec backend python -m ruff check backend/infrastructure/persistence/models/research_memo.py backend/tests/unit/infrastructure/test_research_memo_orm.py
docker compose exec backend python -m ruff format --check backend/infrastructure/persistence/models/research_memo.py backend/tests/unit/infrastructure/test_research_memo_orm.py
```

```bash
git add backend/infrastructure/persistence/models/research_memo.py backend/tests/unit/infrastructure/test_research_memo_orm.py
git commit -m "feat(persistence): ResearchMemoORM SQLAlchemy-Modell (#17, build-step 4/7)

Tabelle research_memos mit 14 Spalten gemäss Foundation-Spec §4:
- id (UUID PK), stock_id+model_run_id (FK CASCADE), language (default 'de')
- created_at (timezone-aware, server_default now())
- 9 LLM-Output-Felder, 3 davon als JSONB (contradictions, key_strengths, key_risks)
- UNIQUE-Constraint uq_research_memos_stock_run_lang
- CHECK-Constraint ck_research_memos_confidence (low/medium/high)
- Index ix_research_memos_model_run_id

12 Schema-Tests RED→GREEN: tablename, alle 14 Spalten, PK, FK CASCADE
auf beiden FKs, timezone-aware created_at, language default, JSONB-Typen,
Nullable-Verhalten, UNIQUE-Constraint mit Name+Cols, CHECK auf confidence,
Index auf model_run_id.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Alembic-Migration

**Files:**
- Create: `backend/alembic/versions/0005_create_research_memos.py`
- Modify: `backend/alembic/env.py` (add ORM-import)

- [ ] **Step 1: Add ORM import to `env.py`**

Find the existing imports of ORM models in `backend/alembic/env.py` and add:

```python
from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM  # noqa: F401
```

(Pattern: ORM muss vor `target_metadata = Base.metadata` importiert werden, sonst kennt Alembic die Tabelle nicht.)

- [ ] **Step 2: Generate migration scaffold (or write manually)**

Manuell, um Kontrolle über Reihenfolge der Defaults zu behalten:

```python
# backend/alembic/versions/0005_create_research_memos.py
"""create research_memos

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_memos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ranking_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(2), nullable=False, server_default="de"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("one_liner", sa.String(150), nullable=False),
        sa.Column("ranking_interpretation", sa.String(600), nullable=False),
        sa.Column("sweet_spot", sa.Boolean, nullable=False),
        sa.Column("sweet_spot_explanation", sa.String(300), nullable=True),
        sa.Column(
            "contradictions",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("key_strengths", postgresql.JSONB, nullable=False),
        sa.Column("key_risks", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "stock_id", "model_run_id", "language",
            name="uq_research_memos_stock_run_lang",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="confidence",
        ),
    )
    op.create_index(
        "ix_research_memos_model_run_id",
        "research_memos",
        ["model_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_memos_model_run_id", table_name="research_memos")
    op.drop_table("research_memos")
```

- [ ] **Step 3: Run upgrade + downgrade roundtrip on live DB**

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic upgrade head
```
Expected: alle 3 Befehle ohne Fehler. Final state hat `alembic_version = 0005` und `research_memos`-Tabelle.

Verify Schema:
```bash
docker compose exec -T db psql -U prisma -d prisma -c "\d research_memos"
```
Expected: 14 Spalten mit korrekten Typen, FK-Constraints, UNIQUE, CHECK, Index sichtbar.

- [ ] **Step 4: Run all existing tests to verify no regression**

```bash
docker compose exec backend pytest backend/tests/ -q
```
Expected: alle vorherigen Tests + neue Schema-Tests grün.

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend python -m ruff check backend/alembic/
docker compose exec backend python -m ruff format --check backend/alembic/
```

```bash
git add backend/alembic/versions/0005_create_research_memos.py backend/alembic/env.py
git commit -m "feat(persistence): Alembic-Migration 0005 für research_memos (#17, build-step 5/7)

Migration erstellt research_memos-Tabelle exakt gemäss ORM-Modell aus
Build-Step 4. Manuell verifiziert mit upgrade+downgrade-Roundtrip auf
Live-DB im docker-compose-Stack:

  alembic upgrade head    → alembic_version=0005, Tabelle erstellt
  alembic downgrade -1    → alembic_version=0004, Tabelle weg
  alembic upgrade head    → 0005 wiederhergestellt

env.py um ResearchMemoORM-Import ergänzt (Auto-Discovery für künftige
autogenerate-Migrations).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: ResearchMemoRepository ABC (Port)

**Files:**
- Create: `backend/domain/repositories/research_memo_repository.py`

(Kein Test-File — ABC ist nicht direkt testbar. Tests kommen mit dem Adapter in Task 7.)

- [ ] **Step 1: Implement Port (kein vorgängiger Test)**

```python
# backend/domain/repositories/research_memo_repository.py
"""Port für ResearchMemo-Persistenz."""
from abc import ABC, abstractmethod
from typing import Literal
from uuid import UUID

from backend.domain.entities.research_memo import ResearchMemo


class ResearchMemoRepository(ABC):
    """Port für ResearchMemo-Persistenz.

    Konkrete Implementierungen in backend/infrastructure/persistence/repositories/.
    """

    @abstractmethod
    async def save(self, memo: ResearchMemo) -> None:
        """Persistiere ODER überschreibe (UPSERT) ein Memo.

        Konflikt-Strategie: bei UNIQUE-Verletzung auf
        (stock_id, model_run_id, language) wird der existierende Eintrag
        überschrieben — alle Schema-Felder, aber NICHT created_at.
        """

    @abstractmethod
    async def get(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        language: Literal["de", "en"] = "de",
    ) -> ResearchMemo | None:
        """Lade existierendes Memo oder None."""
```

- [ ] **Step 2: Verify ABC compiles + can't be instantiated**

```bash
docker compose exec backend python -c "
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
try:
    ResearchMemoRepository()
    print('ERROR: ABC was instantiated')
except TypeError as e:
    print('OK: ABC correctly abstract -', e)
"
```
Expected: `OK: ABC correctly abstract - Can't instantiate abstract class ResearchMemoRepository ...`

- [ ] **Step 3: mypy + ruff**

```bash
docker compose exec backend python -m mypy backend/domain/repositories/research_memo_repository.py
docker compose exec backend python -m ruff check backend/domain/repositories/research_memo_repository.py
docker compose exec backend python -m ruff format --check backend/domain/repositories/research_memo_repository.py
```
Expected: alle 3 grün.

- [ ] **Step 4: Commit**

```bash
git add backend/domain/repositories/research_memo_repository.py
git commit -m "feat(domain): ResearchMemoRepository ABC (Port) (#17, build-step 6/7)

Minimaler Port mit zwei Methoden für PR #1:
- save(memo): UPSERT-Verhalten, created_at bleibt unverändert beim Update
- get(stock_id, model_run_id, language): None wenn nicht existent

list_by_run, delete und exists kommen mit Service in Folge-Issue (YAGNI).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: SQLAResearchMemoRepository (Adapter) + Integration-Tests

**Files:**
- Create: `backend/infrastructure/persistence/repositories/research_memo_repository.py`
- Create: `backend/tests/integration/persistence/__init__.py`
- Create: `backend/tests/integration/persistence/conftest.py` (für DB-Cleanup-Fixture)
- Create: `backend/tests/integration/persistence/test_research_memo_repository.py`

**Pre-check:** Existiert `backend/tests/integration/`-Verzeichnis bereits? Wenn ja, nur `persistence/`-Subdir anlegen. Wenn nein, beides.

```bash
ls backend/tests/integration/ 2>/dev/null || echo "MISSING"
```

- [ ] **Step 1: Write failing integration tests**

```python
# backend/tests/integration/persistence/conftest.py
"""DB-Fixture-Setup für persistence-Integration-Tests."""
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.persistence.session import async_session_factory


@pytest_asyncio.fixture
async def truncate_research_memos() -> AsyncGenerator[None, None]:
    """Per-Test-Cleanup für research_memos-Tabelle."""
    yield
    async with async_session_factory() as session:
        await session.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE research_memos, ranking_runs, stocks "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async-Session für direkte DB-Queries in Tests."""
    async with async_session_factory() as session:
        yield session
```

```python
# backend/tests/integration/persistence/test_research_memo_repository.py
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo
from backend.infrastructure.persistence.repositories.research_memo_repository import (
    SQLAResearchMemoRepository,
)
from backend.infrastructure.persistence.session import async_session_factory


pytestmark = [pytest.mark.integration]


def _new_memo(
    stock_id: uuid.UUID,
    model_run_id: uuid.UUID,
    language: str = "de",
    one_liner: str = "Initialer Memo-Text",
) -> ResearchMemo:
    return ResearchMemo(
        id=uuid.uuid4(),
        stock_id=stock_id,
        model_run_id=model_run_id,
        language=language,  # type: ignore[arg-type]
        created_at=datetime.now(UTC),
        one_liner=one_liner,
        ranking_interpretation="x" * 200,
        sweet_spot=False,
        sweet_spot_explanation=None,
        contradictions=[
            ContradictionItem(model_a="Quality", model_b="Trend", description="x" * 50)
        ],
        key_strengths=["Stabilität"],
        key_risks=["FX"],
        confidence="medium",
        model_version="claude-sonnet-4-6@20260101",
    )


@pytest_asyncio.fixture
async def seed_stock_and_run(db_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Erzeugt Stock + RankingRun, returned (stock_id, model_run_id)."""
    stock_id = uuid.uuid4()
    run_id = uuid.uuid4()
    universe_id = uuid.uuid4()

    await db_session.execute(
        text("INSERT INTO stocks (id, ticker, name, currency) VALUES (:id, 'NESN', 'Nestle', 'CHF')"),
        {"id": stock_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, description) VALUES (:id, 'TEST', 'test universe')"
        ),
        {"id": universe_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO ranking_runs (id, universe_id, status, created_at) "
            "VALUES (:id, :uid, 'completed', now())"
        ),
        {"id": run_id, "uid": universe_id},
    )
    await db_session.commit()
    return stock_id, run_id


class TestRoundtripAndUpsert:
    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_save_then_get_returns_same_memo(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(async_session_factory)
        memo = _new_memo(stock_id, run_id)

        await repo.save(memo)
        got = await repo.get(stock_id, run_id)

        assert got is not None
        assert got.id == memo.id
        assert got.one_liner == memo.one_liner
        assert len(got.contradictions) == 1
        assert got.contradictions[0].model_a == "Quality"

    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_get_nonexistent_returns_none(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(async_session_factory)
        got = await repo.get(stock_id, run_id)
        assert got is None

    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_upsert_overwrites_fields_keeps_created_at(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(async_session_factory)

        memo_v1 = _new_memo(stock_id, run_id, one_liner="erste Version")
        await repo.save(memo_v1)
        got_v1 = await repo.get(stock_id, run_id)
        assert got_v1 is not None
        original_created_at = got_v1.created_at

        memo_v2 = _new_memo(stock_id, run_id, one_liner="zweite Version")
        await repo.save(memo_v2)
        got_v2 = await repo.get(stock_id, run_id)

        assert got_v2 is not None
        assert got_v2.one_liner == "zweite Version"  # überschrieben
        assert got_v2.created_at == original_created_at  # NICHT überschrieben

    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_multi_language_coexists(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(async_session_factory)

        memo_de = _new_memo(stock_id, run_id, language="de", one_liner="Deutsch-Memo")
        memo_en = _new_memo(stock_id, run_id, language="en", one_liner="English memo")

        await repo.save(memo_de)
        await repo.save(memo_en)

        got_de = await repo.get(stock_id, run_id, language="de")
        got_en = await repo.get(stock_id, run_id, language="en")

        assert got_de is not None and got_de.one_liner == "Deutsch-Memo"
        assert got_en is not None and got_en.one_liner == "English memo"


class TestCascade:
    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_delete_stock_cascades_to_memo(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
        db_session: AsyncSession,
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(async_session_factory)

        memo = _new_memo(stock_id, run_id)
        await repo.save(memo)

        await db_session.execute(
            text("DELETE FROM stocks WHERE id = :id"), {"id": stock_id}
        )
        await db_session.commit()

        got = await repo.get(stock_id, run_id)
        assert got is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest backend/tests/integration/persistence/test_research_memo_repository.py -v
```
Expected: FAIL with `ModuleNotFoundError: SQLAResearchMemoRepository`

- [ ] **Step 3: Implement Adapter**

```python
# backend/infrastructure/persistence/repositories/research_memo_repository.py
"""SQLAlchemy-Adapter für ResearchMemoRepository."""
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo
from backend.domain.repositories.research_memo_repository import (
    ResearchMemoRepository,
)
from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM


class SQLAResearchMemoRepository(ResearchMemoRepository):
    """SQLAlchemy-Implementation des ResearchMemoRepository-Ports.

    Eigene session_factory pro Operation (Pattern aus SQLACostLogRepository,
    PR #25) — vermeidet Transaction-Leaks zwischen Request-Handler und
    Repository-Layer.
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def save(self, memo: ResearchMemo) -> None:
        async with self._session_factory() as session:
            stmt = pg_insert(ResearchMemoORM).values(
                id=memo.id,
                stock_id=memo.stock_id,
                model_run_id=memo.model_run_id,
                language=memo.language,
                created_at=memo.created_at,
                one_liner=memo.one_liner,
                ranking_interpretation=memo.ranking_interpretation,
                sweet_spot=memo.sweet_spot,
                sweet_spot_explanation=memo.sweet_spot_explanation,
                contradictions=[c.model_dump() for c in memo.contradictions],
                key_strengths=memo.key_strengths,
                key_risks=memo.key_risks,
                confidence=memo.confidence,
                model_version=memo.model_version,
            ).on_conflict_do_update(
                constraint="uq_research_memos_stock_run_lang",
                set_={
                    "one_liner": memo.one_liner,
                    "ranking_interpretation": memo.ranking_interpretation,
                    "sweet_spot": memo.sweet_spot,
                    "sweet_spot_explanation": memo.sweet_spot_explanation,
                    "contradictions": [c.model_dump() for c in memo.contradictions],
                    "key_strengths": memo.key_strengths,
                    "key_risks": memo.key_risks,
                    "confidence": memo.confidence,
                    "model_version": memo.model_version,
                    # created_at bewusst NICHT im Set — Lifecycle-Marker bleibt
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def get(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        language: Literal["de", "en"] = "de",
    ) -> ResearchMemo | None:
        async with self._session_factory() as session:
            stmt = select(ResearchMemoORM).where(
                ResearchMemoORM.stock_id == stock_id,
                ResearchMemoORM.model_run_id == model_run_id,
                ResearchMemoORM.language == language,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return _orm_to_entity(row) if row else None


def _orm_to_entity(row: ResearchMemoORM) -> ResearchMemo:
    """Mapping ORM-Row → Domain-Entity. JSONB-Listen → Pydantic-Klassen."""
    return ResearchMemo(
        id=row.id,
        stock_id=row.stock_id,
        model_run_id=row.model_run_id,
        language=row.language,  # type: ignore[arg-type]
        created_at=row.created_at,
        one_liner=row.one_liner,
        ranking_interpretation=row.ranking_interpretation,
        sweet_spot=row.sweet_spot,
        sweet_spot_explanation=row.sweet_spot_explanation,
        contradictions=[ContradictionItem(**d) for d in row.contradictions],
        key_strengths=list(row.key_strengths),
        key_risks=list(row.key_risks),
        confidence=row.confidence,  # type: ignore[arg-type]
        model_version=row.model_version,
    )
```

Plus leere `backend/tests/integration/persistence/__init__.py`.

- [ ] **Step 4: Run integration tests**

```bash
docker compose exec backend pytest backend/tests/integration/persistence/test_research_memo_repository.py -v
```
Expected: 5 passed

- [ ] **Step 5: Run ALL tests, verify no regression**

```bash
docker compose exec backend pytest backend/tests/ -q
```
Expected: alle vorherigen + 34 neue (5 ContradictionItem + 11 Schema + 6 Entity + 12 ORM + 5 Repository) → ~182 passed.

- [ ] **Step 6: Lint + commit**

```bash
docker compose exec backend python -m mypy backend/infrastructure/persistence/repositories/research_memo_repository.py backend/tests/integration/persistence/
docker compose exec backend python -m ruff check backend/infrastructure/persistence/repositories/research_memo_repository.py backend/tests/integration/persistence/
docker compose exec backend python -m ruff format --check backend/infrastructure/persistence/repositories/research_memo_repository.py backend/tests/integration/persistence/
```

```bash
git add backend/infrastructure/persistence/repositories/research_memo_repository.py backend/tests/integration/persistence/__init__.py backend/tests/integration/persistence/conftest.py backend/tests/integration/persistence/test_research_memo_repository.py
git commit -m "feat(persistence): SQLAResearchMemoRepository Adapter + Integration-Tests (#17, build-step 7/7)

Async SQLAlchemy-Implementation mit pg_insert.on_conflict_do_update für
UPSERT-Semantik. created_at bewusst NICHT im UPDATE-Set
(Lifecycle-Marker). JSONB-Serialisierung im Adapter (Schema-Mapping
via _orm_to_entity).

Eigene session_factory pro Operation (Pattern aus SQLACostLogRepository,
PR #25) — vermeidet Transaction-Leaks.

5 Integration-Tests gegen Live-Postgres im docker-compose-Stack:
- Roundtrip Save→Get
- Get nicht-existent → None
- UPSERT überschreibt Schema-Felder, behält created_at
- Multi-Language-Koexistenz (de + en für gleiche stock/run)
- FK-Cascade (Stock löschen → Memos weg)

Neue Test-Konvention: backend/tests/integration/persistence/ mit
conftest.py-Fixture truncate_research_memos für Per-Test-Cleanup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final Steps

- [ ] **Step F1: AI-USAGE-Eintrag schreiben + commit**

Hinzufügen oben in `docs/AI-USAGE.md`, oberhalb des heutigen Foundation-Spec-Eintrags vom 2026-04-30:

```markdown
## 2026-04-30 · Narrative-Engine Foundation Implementation (PR Issue #17)
- **Agent**: Claude Code (Opus 4.7, 1M-Kontext) im Haupt-Context, reine TDD-Loop ohne Subagent.
- **Scope**: 7 Build-Steps für Foundation der Narrative-Engine: ContradictionItem (Value-Object), ResearchMemoSchema (LLM-Vertrag), ResearchMemo Entity, ResearchMemoORM + Migration, Repository Port + SQLA-Adapter. ~34 neue Tests, mypy strict + ruff clean.
- **Was gut lief**: [Sheyla füllt nach Implementierung aus]
- **Was nicht klappte**: [Sheyla füllt nach Implementierung aus]
- **Methodisches Mini-Learning**: [Sheyla füllt nach Implementierung aus]
- **Autor**: Sheyla Sampietro (mit Claude Code)
```

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): Eintrag zur Narrative-Engine-Foundation-Implementation (#17)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step F2: Push + PR erstellen**

```bash
git push -u origin feat/017-narrative-engine
gh pr create --title "feat(ai): Narrative-Engine Foundation — Schema, Entity, Repository (#17)" --body "..."
```

PR-Body-Vorlage (anpassen nach Bedarf):
```markdown
## Summary

Foundation für Narrative-Engine Layer 1 — Issue #17. Spec: `docs/specs/2026-04-30-narrative-engine-foundation.md`.

7 Build-Steps in TDD-Disziplin:
1. ContradictionItem (Value-Object)
2. ResearchMemoSchema (LLM-Vertrag)
3. ResearchMemo Entity (Domain)
4. ResearchMemoORM (SQLAlchemy)
5. Alembic-Migration 0005 (upgrade+downgrade verifiziert)
6. ResearchMemoRepository Port (ABC)
7. SQLAResearchMemoRepository Adapter + Integration-Tests

## Test plan
- [x] mypy strict grün
- [x] ruff check + format clean
- [x] pytest grün (alle 148 vorherigen + ~34 neue = ~182)
- [x] Coverage Domain ≥95%, Infrastructure ≥85%
- [x] Migration upgrade+downgrade-Roundtrip auf Live-DB verifiziert

## Out of Scope (Folge-Issues)
- NarrativeService + Schema→Entity-Mapping
- ClaudeLLMClient-Erweiterung um Memo-Generation
- Prompt-Templates (Jinja2)
- 4 REST-Endpoints aus Master-Spec §8
- Fixture-Mode + Golden-Prompt-Workflow

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Self-Review Checkliste

Nach Abschluss aller Tasks:

- [ ] Alle 7 Tasks committed, jeder auf eigenem TDD-Cycle
- [ ] `pytest backend/tests/` zeigt ~182 passed, 6 skipped
- [ ] `mypy --strict` 0 Fehler
- [ ] `ruff check` + `ruff format --check` clean
- [ ] Migration 0005 ist auf Live-DB applied
- [ ] Spec-Akzeptanz-Kriterien §9 alle abgehakt
- [ ] AI-USAGE-Eintrag mit Final-Reflection von Sheyla ergänzt
- [ ] PR erstellt und Reviewer angefragt
