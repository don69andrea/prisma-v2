# Multi-Memo Batch Implementation Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** Implementiert Async-Job-Batch für Memo-Generierung über Top-N Stocks eines Runs (siehe Spec `2026-05-08-narrative-engine-multi-memo-batch.md`).

**Architektur:** Hexagonal — neue Job-Entity + Repository in Domain/Infra, Service-Erweiterung um Background-Worker-Pattern (asyncio.create_task + Semaphore + session_factory pro Worker), zwei neue REST-Endpoints. Wiederverwendung der bestehenden `generate_memo`-Logik via privatem Helper `_generate_memo_isolated`, der explizit Repos akzeptiert (für Worker mit isolierten DB-Sessions).

**Tech-Stack:** Python 3.12, SQLAlchemy 2.0 (async), Alembic, FastAPI, Pydantic v2, Anthropic SDK (existing LLMClient-Wrapper). Keine neuen Dependencies.

---

## Reality-Check vor Implementation

- [x] **Existing `generate_memo` Spec-Drift-Check (B3, PR #64):** `generate_memo` returnt nach Reload aus DB, nicht in-memory entity. Worker-Pfad muss das berücksichtigen.
- [x] **Session-Factory-Pattern:** `SQLAResearchMemoRepository(session_factory=...)` ist bereits etabliert. `SQLAStockRepository(session=...)` und `SQLARankingRunRepository(session=...)` haben aktuell nur Session-Variante — Worker baut die Repos ad-hoc innerhalb von `async with session_factory()`-Block.
- [x] **B1-Lehre:** `asyncio.gather` darf NICHT mit shared session laufen. Jeder Worker hat eigene Session via session_factory.
- [x] **EN-Guard (B2):** Existiert in `generate_memo`. `start_batch` braucht eigenen EN-Guard *vor* DB-Write/Job-Spawn.
- [x] **Cost-Tracking:** `LLMClient.messages_create` schreibt CostLog automatisch via `feature` parameter. Im Batch-Worker also unverändert.

---

## Task 1: Domain-Entity `MemoBatchJob`

**Files:**
- Create: `backend/domain/entities/memo_batch_job.py`
- Test: `backend/tests/unit/domain/entities/test_memo_batch_job.py`

- [ ] **Step 1: Test schreiben (RED-Phase)**

```python
# backend/tests/unit/domain/entities/test_memo_batch_job.py
"""Tests fuer MemoBatchJob Entity."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.domain.entities.memo_batch_job import MemoBatchJob

pytestmark = pytest.mark.unit


def _valid_payload() -> dict[str, Any]:
    return {
        "id": uuid4(),
        "model_run_id": uuid4(),
        "top_n": 20,
        "language": "de",
        "status": "pending",
        "failed_stock_ids": [],
        "error_message": None,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
    }


class TestMemoBatchJobValid:
    def test_minimal_valid(self) -> None:
        job = MemoBatchJob(**_valid_payload())
        assert job.status == "pending"
        assert job.top_n == 20
        assert job.failed_stock_ids == []

    def test_failed_stock_ids_default_empty(self) -> None:
        payload = _valid_payload()
        del payload["failed_stock_ids"]
        job = MemoBatchJob(**payload)
        assert job.failed_stock_ids == []


class TestMemoBatchJobFrozen:
    def test_is_frozen(self) -> None:
        job = MemoBatchJob(**_valid_payload())
        with pytest.raises(ValidationError):
            job.status = "running"  # type: ignore[misc]


class TestMemoBatchJobConstraints:
    def test_top_n_too_low_raises(self) -> None:
        payload = _valid_payload()
        payload["top_n"] = 0
        with pytest.raises(ValidationError):
            MemoBatchJob(**payload)

    def test_top_n_too_high_raises(self) -> None:
        payload = _valid_payload()
        payload["top_n"] = 101
        with pytest.raises(ValidationError):
            MemoBatchJob(**payload)

    def test_invalid_status_raises(self) -> None:
        payload = _valid_payload()
        payload["status"] = "unknown"
        with pytest.raises(ValidationError):
            MemoBatchJob(**payload)

    def test_invalid_language_raises(self) -> None:
        payload = _valid_payload()
        payload["language"] = "fr"
        with pytest.raises(ValidationError):
            MemoBatchJob(**payload)
```

- [ ] **Step 2: RED verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/domain/entities/test_memo_batch_job.py -v
```
Expected: `ImportError: cannot import name 'MemoBatchJob'` oder collection-error → 0 passed.

- [ ] **Step 3: Entity implementieren**

```python
# backend/domain/entities/memo_batch_job.py
"""MemoBatchJob — Job-Entity fuer asynchrone Multi-Memo-Generierung.

Spec: docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md §4
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MemoBatchJob(BaseModel):
    """Job-State fuer einen Multi-Memo-Batch-Run.

    Status-Lifecycle:
        pending → running → complete | partial | failed
    """

    model_config = {"frozen": True}

    id: UUID
    model_run_id: UUID
    top_n: int = Field(..., ge=1, le=100)
    language: Literal["de", "en"]
    status: Literal["pending", "running", "complete", "partial", "failed"]
    failed_stock_ids: list[UUID] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/domain/entities/test_memo_batch_job.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Lint + Format + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && ruff format --check backend/ && mypy backend/
```
Expected: All checks passed!

- [ ] **Step 6: Commit**

```bash
git add backend/domain/entities/memo_batch_job.py backend/tests/unit/domain/entities/test_memo_batch_job.py
git commit -m "feat(domain): MemoBatchJob Entity (Multi-Memo Batch, build-step 1/12)

Frozen Pydantic-Entity mit Status-Lifecycle (pending → running →
complete/partial/failed). top_n constraint 1-100, Literal language
de/en, failed_stock_ids als list[UUID].

Spec: docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md §4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Repository-Port `MemoBatchJobRepository`

**Files:**
- Create: `backend/domain/repositories/memo_batch_job_repository.py`

- [ ] **Step 1: Port als ABC implementieren**

```python
# backend/domain/repositories/memo_batch_job_repository.py
"""Port fuer MemoBatchJob-Persistenz."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.memo_batch_job import MemoBatchJob


class MemoBatchJobRepository(ABC):
    """Abstrakte Schnittstelle fuer Job-State-Persistenz.

    UPSERT-Semantik: bei Konflikt werden id und created_at als
    Lifecycle-Marker NICHT ueberschrieben (analog research_memos).
    """

    @abstractmethod
    async def save(self, job: MemoBatchJob) -> None:
        """Persistiert oder aktualisiert einen Job."""

    @abstractmethod
    async def get(self, job_id: UUID) -> MemoBatchJob | None:
        """Laedt einen Job per ID, oder None wenn unknown."""
```

- [ ] **Step 2: Lint + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && mypy backend/
```
Expected: All checks passed!

- [ ] **Step 3: Commit**

```bash
git add backend/domain/repositories/memo_batch_job_repository.py
git commit -m "feat(domain): MemoBatchJobRepository Port (build-step 2/12)

Abstrakte Schnittstelle fuer Job-State-Persistenz. UPSERT-Semantik
analog research_memos (id und created_at als Lifecycle-Marker).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: ORM-Model + Alembic-Migration

**Files:**
- Create: `backend/infrastructure/persistence/models/memo_batch_job.py`
- Test: `backend/tests/unit/infrastructure/test_memo_batch_job_orm.py`
- Create (via alembic): `alembic/versions/0007_memo_batch_jobs.py`

- [ ] **Step 1: ORM-Test schreiben**

```python
# backend/tests/unit/infrastructure/test_memo_batch_job_orm.py
"""ORM-Schema-Tests fuer memo_batch_jobs Tabelle."""

import pytest
from sqlalchemy import inspect

from backend.infrastructure.persistence.base import Base
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
    fks = {fk.column.table.name for fk in inspect(MemoBatchJobORM).columns["model_run_id"].foreign_keys}
    assert "ranking_runs" in fks


def test_id_is_primary_key() -> None:
    pk_cols = {c.name for c in inspect(MemoBatchJobORM).primary_key}
    assert pk_cols == {"id"}


def test_check_constraints_named() -> None:
    """Naming-Convention prefix muss die Constraint-Namen NICHT verdoppeln
    (Lehre aus PR #54 Foundation Build-Step 5)."""
    constraints = MemoBatchJobORM.__table__.constraints
    check_names = {c.name for c in constraints if c.name and c.name.startswith("ck_")}
    # Erwarte ck_memo_batch_jobs_top_n, ck_memo_batch_jobs_language, ck_memo_batch_jobs_status
    assert any("top_n" in n for n in check_names)
    assert any("language" in n for n in check_names)
    assert any("status" in n for n in check_names)
    # KEINE doppelten "ck_memo_batch_jobs_ck_memo_batch_jobs_..."-Namen
    for name in check_names:
        assert "ck_memo_batch_jobs_ck_memo_batch_jobs" not in name
```

- [ ] **Step 2: RED verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/infrastructure/test_memo_batch_job_orm.py -v
```
Expected: ImportError für `MemoBatchJobORM`.

- [ ] **Step 3: ORM-Model implementieren**

```python
# backend/infrastructure/persistence/models/memo_batch_job.py
"""ORM-Mapping fuer memo_batch_jobs Tabelle."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class MemoBatchJobORM(Base):
    """SQLA-Mapping fuer memo_batch_jobs.

    UPSERT via pg_insert.on_conflict_do_update mit id und created_at
    als Lifecycle-Marker (nicht im set_).
    """

    __tablename__ = "memo_batch_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    model_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ranking_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    top_n: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failed_stock_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("top_n BETWEEN 1 AND 100", name="top_n"),
        CheckConstraint("language IN ('de', 'en')", name="language"),
        CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'partial', 'failed')",
            name="status",
        ),
    )
```

**Wichtig (Lehre PR #54 Build-Step 5):** Constraint-Names sind nur die Suffix-Teile (`top_n`, nicht `ck_memo_batch_jobs_top_n`) — das `NAMING_CONVENTION` aus `base.py` wickelt den Prefix automatisch ein.

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/infrastructure/test_memo_batch_job_orm.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Alembic-Migration generieren**

```bash
source .venv/bin/activate && alembic revision -m "create memo_batch_jobs"
```

Erwartete Datei: `alembic/versions/0007_<hash>_create_memo_batch_jobs.py` (umbenennen zu `0007_memo_batch_jobs.py`).

- [ ] **Step 6: Migration manuell editieren**

```python
# alembic/versions/0007_memo_batch_jobs.py
"""create memo_batch_jobs

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memo_batch_jobs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "model_run_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("ranking_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("top_n", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "failed_stock_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("top_n BETWEEN 1 AND 100", name="ck_memo_batch_jobs_top_n"),
        sa.CheckConstraint("language IN ('de', 'en')", name="ck_memo_batch_jobs_language"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'partial', 'failed')",
            name="ck_memo_batch_jobs_status",
        ),
    )
    op.create_index(
        "ix_memo_batch_jobs_model_run_id",
        "memo_batch_jobs",
        ["model_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memo_batch_jobs_model_run_id", table_name="memo_batch_jobs")
    op.drop_table("memo_batch_jobs")
```

- [ ] **Step 7: Migration-Roundtrip verifizieren**

```bash
source .venv/bin/activate && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```
Expected: 3 successful runs (upgrade → downgrade → upgrade).

- [ ] **Step 8: Lint + Format + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && ruff format --check backend/ && mypy backend/
```
Expected: All checks passed!

- [ ] **Step 9: Commit**

```bash
git add backend/infrastructure/persistence/models/memo_batch_job.py backend/tests/unit/infrastructure/test_memo_batch_job_orm.py alembic/versions/0007_memo_batch_jobs.py
git commit -m "feat(persistence): memo_batch_jobs Tabelle + ORM (build-step 3/12)

ORM-Model mit FK zu ranking_runs (CASCADE), CHECK-Constraints fuer top_n,
language, status. JSONB fuer failed_stock_ids. Naming-Convention-Suffix
in __table_args__ (analog Foundation PR #54).

Alembic-Migration 0007 mit upgrade/downgrade-Roundtrip verifiziert.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: SQLA-Adapter `SQLAMemoBatchJobRepository`

**Files:**
- Create: `backend/infrastructure/persistence/repositories/memo_batch_job_repository.py`
- Test: `backend/tests/integration/persistence/test_memo_batch_job_repository.py`

- [ ] **Step 1: Integration-Test schreiben**

```python
# backend/tests/integration/persistence/test_memo_batch_job_repository.py
"""Integration-Tests fuer SQLAMemoBatchJobRepository (echtes PG)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.infrastructure.persistence.repositories.memo_batch_job_repository import (
    SQLAMemoBatchJobRepository,
)
from backend.infrastructure.persistence.session import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _seed_run(session_factory) -> uuid4:
    """Erstellt einen minimalen ranking_run fuer FK-Constraints."""
    run_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO ranking_runs (id, universe_id, status, created_at) "
                "VALUES (:id, :uid, 'completed', NOW())"
            ),
            {"id": run_id, "uid": uuid4()},
        )
        # universes-Insert fuer FK
        await session.commit()
    return run_id


def _make_job(run_id, **overrides) -> MemoBatchJob:
    payload = {
        "id": uuid4(),
        "model_run_id": run_id,
        "top_n": 20,
        "language": "de",
        "status": "pending",
        "failed_stock_ids": [],
        "error_message": None,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
    }
    payload.update(overrides)
    return MemoBatchJob(**payload)


class TestRoundtripAndUpsert:
    async def test_save_then_get_returns_same_job(self, integration_db) -> None:
        # integration_db fixture seeded universe + run; provides run_id
        repo = SQLAMemoBatchJobRepository(session_factory=get_session_factory())
        job = _make_job(integration_db.run_id)

        await repo.save(job)
        loaded = await repo.get(job.id)

        assert loaded is not None
        assert loaded.id == job.id
        assert loaded.status == "pending"
        assert loaded.top_n == 20

    async def test_get_unknown_returns_none(self, integration_db) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory=get_session_factory())
        loaded = await repo.get(uuid4())
        assert loaded is None

    async def test_upsert_preserves_id_and_created_at(self, integration_db) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory=get_session_factory())
        original = _make_job(integration_db.run_id)
        await repo.save(original)

        # Update mit gleicher id, neuem status + completed_at
        updated = original.model_copy(
            update={
                "status": "complete",
                "completed_at": datetime.now(UTC),
                "created_at": datetime.now(UTC),  # versuche zu ueberschreiben
            }
        )
        await repo.save(updated)

        loaded = await repo.get(original.id)
        assert loaded is not None
        assert loaded.status == "complete"
        # created_at darf NICHT veraendert sein (Lifecycle-Marker)
        assert loaded.created_at == original.created_at

    async def test_failed_stock_ids_jsonb_roundtrip(self, integration_db) -> None:
        repo = SQLAMemoBatchJobRepository(session_factory=get_session_factory())
        stock_ids = [uuid4(), uuid4(), uuid4()]
        job = _make_job(integration_db.run_id, failed_stock_ids=stock_ids, status="partial")
        await repo.save(job)

        loaded = await repo.get(job.id)
        assert loaded is not None
        assert loaded.failed_stock_ids == stock_ids
```

**Hinweis:** `integration_db` fixture muss Universe + Run + (für spätere Tests) Stocks vorseeden. Das fixture pattern ist analog zu `test_research_memo_repository.py` — bei Implementation referenzieren und ggf. erweitern.

- [ ] **Step 2: RED verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/integration/persistence/test_memo_batch_job_repository.py -v
```
Expected: ImportError für `SQLAMemoBatchJobRepository`.

- [ ] **Step 3: SQLA-Adapter implementieren**

```python
# backend/infrastructure/persistence/repositories/memo_batch_job_repository.py
"""SQLA-Adapter fuer MemoBatchJobRepository."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.domain.repositories.memo_batch_job_repository import (
    MemoBatchJobRepository,
)
from backend.infrastructure.persistence.models.memo_batch_job import (
    MemoBatchJobORM,
)


class SQLAMemoBatchJobRepository(MemoBatchJobRepository):
    """SQLAlchemy-Adapter mit eigener session_factory.

    Eigene Session pro Operation (analog SQLAResearchMemoRepository) —
    nicht an Request-Session gebunden, da Background-Worker auch
    persistieren.
    """

    def __init__(
        self,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    ) -> None:
        self._session_factory = session_factory

    async def save(self, job: MemoBatchJob) -> None:
        async with self._session_factory() as session:
            stmt = pg_insert(MemoBatchJobORM).values(
                id=job.id,
                model_run_id=job.model_run_id,
                top_n=job.top_n,
                language=job.language,
                status=job.status,
                failed_stock_ids=[str(uid) for uid in job.failed_stock_ids],
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
            # UPSERT: id und created_at sind Lifecycle-Marker, nicht im set_
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": stmt.excluded.status,
                    "failed_stock_ids": stmt.excluded.failed_stock_ids,
                    "error_message": stmt.excluded.error_message,
                    "started_at": stmt.excluded.started_at,
                    "completed_at": stmt.excluded.completed_at,
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def get(self, job_id: UUID) -> MemoBatchJob | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(MemoBatchJobORM).where(MemoBatchJobORM.id == job_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return MemoBatchJob(
                id=row.id,
                model_run_id=row.model_run_id,
                top_n=row.top_n,
                language=row.language,  # type: ignore[arg-type]
                status=row.status,  # type: ignore[arg-type]
                failed_stock_ids=[UUID(s) for s in row.failed_stock_ids],
                error_message=row.error_message,
                created_at=row.created_at,
                started_at=row.started_at,
                completed_at=row.completed_at,
            )
```

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/integration/persistence/test_memo_batch_job_repository.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Lint + Format + Mypy + Full Suite**

```bash
source .venv/bin/activate && ruff check backend/ && ruff format --check backend/ && mypy backend/ && python -m pytest backend/tests -q
```
Expected: All clean, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/infrastructure/persistence/repositories/memo_batch_job_repository.py backend/tests/integration/persistence/test_memo_batch_job_repository.py
git commit -m "feat(persistence): SQLAMemoBatchJobRepository (build-step 4/12)

UPSERT-Adapter via pg_insert.on_conflict_do_update. id und created_at
als Lifecycle-Marker (nicht im set_, analog research_memos).
session_factory pro Operation (eigene Transaktion, nicht request-bound).

failed_stock_ids als JSONB serialisiert (UUID -> str), beim get
deserialisiert.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: ResearchMemoRepository erweitern um `list_by_run`

**Files:**
- Modify: `backend/domain/repositories/research_memo_repository.py`
- Modify: `backend/infrastructure/persistence/repositories/research_memo_repository.py`
- Modify: `backend/tests/integration/persistence/test_research_memo_repository.py` (Tests erweitern)

- [ ] **Step 1: Test schreiben**

```python
# backend/tests/integration/persistence/test_research_memo_repository.py (erweitern)
# Am Ende der Datei hinzufuegen:

class TestListByRun:
    async def test_list_by_run_returns_memos_in_total_rank_order(
        self, integration_db
    ) -> None:
        repo = SQLAResearchMemoRepository(session_factory=get_session_factory())
        run_id = integration_db.run_id

        # 3 memos seeden (verschiedene stocks im selben run)
        memos = [
            _make_memo(stock_id=uuid4(), run_id=run_id, one_liner=f"Memo {i}")
            for i in range(3)
        ]
        for m in memos:
            await repo.save(m)

        loaded = await repo.list_by_run(run_id, language="de")
        assert len(loaded) == 3
        # Reihenfolge: created_at ASC (oder beliebig — Service sortiert spaeter)
        assert {m.id for m in loaded} == {m.id for m in memos}

    async def test_list_by_run_filters_language(self, integration_db) -> None:
        repo = SQLAResearchMemoRepository(session_factory=get_session_factory())
        run_id = integration_db.run_id

        de_memo = _make_memo(stock_id=uuid4(), run_id=run_id, language="de")
        en_memo = _make_memo(stock_id=uuid4(), run_id=run_id, language="en")
        await repo.save(de_memo)
        await repo.save(en_memo)

        de_only = await repo.list_by_run(run_id, language="de")
        assert len(de_only) == 1
        assert de_only[0].id == de_memo.id

    async def test_list_by_run_empty_when_no_memos(self, integration_db) -> None:
        repo = SQLAResearchMemoRepository(session_factory=get_session_factory())
        loaded = await repo.list_by_run(uuid4(), language="de")
        assert loaded == []
```

- [ ] **Step 2: Port erweitern**

```python
# backend/domain/repositories/research_memo_repository.py
# Methode hinzufuegen:

@abstractmethod
async def list_by_run(
    self,
    model_run_id: UUID,
    *,
    language: Literal["de", "en"] = "de",
) -> list[ResearchMemo]:
    """Liefert alle Memos fuer einen Run + Sprache, leere Liste wenn keine."""
```

- [ ] **Step 3: Adapter erweitern**

```python
# backend/infrastructure/persistence/repositories/research_memo_repository.py
# Methode hinzufuegen:

async def list_by_run(
    self,
    model_run_id: UUID,
    *,
    language: Literal["de", "en"] = "de",
) -> list[ResearchMemo]:
    async with self._session_factory() as session:
        result = await session.execute(
            select(ResearchMemoORM)
            .where(ResearchMemoORM.model_run_id == model_run_id)
            .where(ResearchMemoORM.language == language)
            .order_by(ResearchMemoORM.created_at.asc())
        )
        rows = result.scalars().all()
        return [self._to_entity(row) for row in rows]
```

(Nutzt existing `_to_entity`-Helper, falls vorhanden — sonst inline mappen wie in `get`.)

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/integration/persistence/test_research_memo_repository.py -v
```
Expected: alle bestehenden + 3 neue Tests passed.

- [ ] **Step 5: Lint + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && mypy backend/
```
Expected: All clean.

- [ ] **Step 6: Commit**

```bash
git add backend/domain/repositories/research_memo_repository.py backend/infrastructure/persistence/repositories/research_memo_repository.py backend/tests/integration/persistence/test_research_memo_repository.py
git commit -m "feat(persistence): ResearchMemoRepository.list_by_run (build-step 5/12)

Neue Methode liefert alle Memos fuer einen run_id + language, sortiert
nach created_at ASC. Wird vom Multi-Memo-Batch fuer GET /jobs/{id}
genutzt (memos[]-Liste in der Response).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: NarrativeService — `_generate_memo_isolated` Helper + Refactor `generate_memo`

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service.py` (verifizieren dass refactor nichts bricht)

- [ ] **Step 1: Pre-Check — bestehende Tests laufen**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service.py -v
```
Expected: alle passed (Baseline vor Refactor).

- [ ] **Step 2: `_generate_memo_isolated` als private Helper extrahieren**

Schritt: Logik aus `generate_memo` in einen privaten Helper auslagern, der `stock_repo` + `run_repo` als optionale kwargs akzeptiert. `generate_memo` ruft den Helper mit Service-internen Repos auf.

```python
# backend/application/services/narrative_service.py
# Innerhalb class NarrativeService:

async def generate_memo(
    self,
    stock_id: UUID,
    model_run_id: UUID,
    *,
    language: Literal["de", "en"] = "de",
    force_regenerate: bool = False,
) -> ResearchMemo:
    return await self._generate_memo_isolated(
        stock_id,
        model_run_id,
        language=language,
        force_regenerate=force_regenerate,
        stock_repo=self._stock_repo,
        run_repo=self._run_repo,
    )

async def _generate_memo_isolated(
    self,
    stock_id: UUID,
    model_run_id: UUID,
    *,
    language: Literal["de", "en"] = "de",
    force_regenerate: bool = False,
    stock_repo: StockRepository,
    run_repo: RankingRunRepository,
) -> ResearchMemo:
    """Memo-Generation mit explizit injizierten Repos.

    Public generate_memo nutzt Service-Repos. Background-Worker
    (_execute_batch) nutzt isolated Repos via session_factory pro
    Worker (B1-Lehre — geteilte AsyncSession ist nicht concurrent-safe).
    """
    # EN-Guard
    if language == "en":
        raise NotImplementedError(
            "EN-Memos sind in dieser Slice noch nicht implementiert "
            "(narrative_system.en.md.j2 ist Stub). Bitte language='de' nutzen."
        )

    # 1. Cache check
    if not force_regenerate:
        existing = await self._memo_repo.get(stock_id, model_run_id, language=language)
        if existing is not None:
            return existing

    # 2. Daten laden + 404-Pfade (sequenziell, Spec §4)
    stock = await stock_repo.get(stock_id)
    if stock is None:
        raise LookupError(f"Stock {stock_id} not found")
    results = await run_repo.get_results(model_run_id)
    if results is None:
        raise LookupError(f"Run {model_run_id} not found")

    try:
        ranking = _extract_ranking_for_ticker(results, ticker=stock.ticker)
    except KeyError as exc:
        raise LookupError(f"Stock {stock.ticker} not in run {model_run_id}") from exc

    universe_context = _build_universe_context(results)

    # 3. Prompts rendern
    system_prompt = self._prompts.render(f"narrative_system.{language}.md.j2", {})
    user_prompt = self._prompts.render(
        "narrative_user.md.j2",
        {
            "ticker": stock.ticker,
            "name": stock.name,
            "sector": stock.sector,
            "country": stock.country,
            "run_id": str(model_run_id),
            "universe_name": "Universe",
            "n_stocks": universe_context.n_stocks,
            "median_rank": universe_context.median_rank,
            "top20_threshold": universe_context.top20_threshold,
            "rankings": _rankings_for_template(ranking),
            "total_rank": ranking["total_rank"],
            "sweet_spot": ranking["is_sweet_spot"],
            "weights": "equal-weighted (0.20 each)",
        },
    )

    # 4. LLM-Call mit Tool-use + Caching
    response = await self._llm.messages_create(
        model=self._model,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        tools=[
            {
                "name": "submit_memo",
                "description": "Submit the structured research memo.",
                "input_schema": ResearchMemoSchema.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "submit_memo"},
        max_tokens=2000,
        feature="narrative_engine",
    )

    # 5. Tool-use Antwort -> Pydantic-Validate (oder Error-Memo-Pfad)
    memo_schema = self._try_validate_tool_response(response)
    if memo_schema is None:
        self._dump_malformed_response(response, stock_id=stock_id, run_id=model_run_id)
        memo_schema = self._build_error_memo_schema(stock=stock, ranking=ranking)

    # 6. Persist
    memo_entity = ResearchMemo(
        id=uuid4(),
        stock_id=stock_id,
        model_run_id=model_run_id,
        language=language,
        created_at=datetime.now(tz=UTC),
        one_liner=memo_schema.one_liner,
        ranking_interpretation=memo_schema.ranking_interpretation,
        sweet_spot=memo_schema.sweet_spot,
        sweet_spot_explanation=memo_schema.sweet_spot_explanation,
        contradictions=list(memo_schema.contradictions),
        key_strengths=list(memo_schema.key_strengths),
        key_risks=list(memo_schema.key_risks),
        confidence=memo_schema.confidence,
        model_version=memo_schema.model_version,
    )
    await self._memo_repo.save(memo_entity)

    # 7. B3: Reload nach save() — UPSERT behaelt Original-id und created_at
    persisted = await self._memo_repo.get(stock_id, model_run_id, language=language)
    if persisted is None:
        raise RuntimeError(
            f"Memo for stock {stock_id} / run {model_run_id} verschwand "
            "zwischen save() und reload — DB-Inkonsistenz?"
        )
    return persisted
```

- [ ] **Step 3: Tests laufen — Refactor darf nichts brechen**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service.py -v
```
Expected: alle passed (gleicher Stand wie vor Refactor).

- [ ] **Step 4: Lint + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && mypy backend/
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/narrative_service.py
git commit -m "refactor(narrative): _generate_memo_isolated als private Helper (build-step 6/12)

Vorbereitung fuer Multi-Memo-Batch: Helper akzeptiert stock_repo und
run_repo als kwargs. Public generate_memo ruft mit Service-Repos auf
(Verhalten unveraendert), Batch-Worker wird mit isolated Repos
aufrufen (B1-Lehre — eigene Sessions pro Worker).

Bestehende Tests laufen unveraendert.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: NarrativeService — `start_batch`

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Create: `backend/tests/unit/application/test_narrative_service_batch.py`
- Modify: `backend/config.py` (Settings erweitern)

- [ ] **Step 1: Settings erweitern**

```python
# backend/config.py — innerhalb class Settings:

max_concurrent_batch_workers: int = 3
stale_batch_timeout_seconds: int = 600
```

- [ ] **Step 2: Test fuer `start_batch` schreiben**

```python
# backend/tests/unit/application/test_narrative_service_batch.py
"""Unit-Tests fuer NarrativeService Multi-Memo-Batch-Methoden."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.memo_batch_job import MemoBatchJob

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_service(
    memo_repo: Any = None,
    run_repo: Any = None,
    stock_repo: Any = None,
    batch_repo: Any = None,
    llm: Any = None,
    prompt_loader: Any = None,
    cost_tracker: Any = None,
    session_factory: Any = None,
) -> NarrativeService:
    return NarrativeService(
        memo_repository=memo_repo or AsyncMock(),
        run_repository=run_repo or AsyncMock(),
        stock_repository=stock_repo or AsyncMock(),
        batch_repository=batch_repo or AsyncMock(),
        llm_client=llm or AsyncMock(),
        prompt_loader=prompt_loader or AsyncMock(),
        cost_tracker=cost_tracker or AsyncMock(),
        session_factory=session_factory or Mock(),
        max_concurrent_batch_workers=3,
        stale_batch_timeout_seconds=600,
    )


class TestStartBatch:
    async def test_start_batch_creates_pending_job(self, monkeypatch) -> None:
        run_repo = AsyncMock()
        run_repo.get_results = AsyncMock(return_value=[{"ticker": "X"}])  # run exists
        batch_repo = AsyncMock()
        cost_tracker = AsyncMock()
        cost_tracker.check_cap = AsyncMock()

        # asyncio.create_task mocken (kein Background-Lauf im Test)
        monkeypatch.setattr("asyncio.create_task", lambda coro: coro.close() or None)

        service = _make_service(
            run_repo=run_repo, batch_repo=batch_repo, cost_tracker=cost_tracker
        )
        run_id = uuid4()

        job = await service.start_batch(run_id, top_n=20)

        assert job.status == "pending"
        assert job.model_run_id == run_id
        assert job.top_n == 20
        assert job.language == "de"
        batch_repo.save.assert_awaited_once()

    async def test_start_batch_raises_for_en_language(self) -> None:
        service = _make_service()
        with pytest.raises(NotImplementedError, match="en"):
            await service.start_batch(uuid4(), language="en")

    async def test_start_batch_raises_404_when_run_missing(self) -> None:
        run_repo = AsyncMock()
        run_repo.get_results = AsyncMock(return_value=None)
        service = _make_service(run_repo=run_repo)

        with pytest.raises(LookupError, match="Run"):
            await service.start_batch(uuid4())

    async def test_start_batch_pre_checks_budget_cap(self, monkeypatch) -> None:
        from backend.domain.errors import BudgetCapExceededError

        run_repo = AsyncMock()
        run_repo.get_results = AsyncMock(return_value=[{"ticker": "X"}])
        cost_tracker = AsyncMock()
        cost_tracker.check_cap = AsyncMock(side_effect=BudgetCapExceededError("over"))

        service = _make_service(run_repo=run_repo, cost_tracker=cost_tracker)

        with pytest.raises(BudgetCapExceededError):
            await service.start_batch(uuid4(), top_n=20)

    async def test_start_batch_validates_top_n_bounds(self) -> None:
        service = _make_service()

        with pytest.raises(ValueError, match="top_n"):
            await service.start_batch(uuid4(), top_n=0)
        with pytest.raises(ValueError, match="top_n"):
            await service.start_batch(uuid4(), top_n=101)
```

- [ ] **Step 3: RED verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service_batch.py -v
```
Expected: Tests failen (Service hat noch kein `start_batch`, kein `batch_repository` im `__init__`).

- [ ] **Step 4: Service-Konstruktor erweitern**

```python
# backend/application/services/narrative_service.py
# class NarrativeService.__init__ erweitern:

def __init__(
    self,
    *,
    memo_repository: ResearchMemoRepository,
    run_repository: RankingRunRepository,
    stock_repository: StockRepository,
    batch_repository: MemoBatchJobRepository,
    llm_client: LLMClient,
    prompt_loader: PromptTemplateLoader,
    cost_tracker: CostTracker,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    max_concurrent_batch_workers: int = 3,
    stale_batch_timeout_seconds: int = 600,
    model: str = "claude-sonnet-4-6",
) -> None:
    self._memo_repo = memo_repository
    self._run_repo = run_repository
    self._stock_repo = stock_repository
    self._batch_repo = batch_repository
    self._llm = llm_client
    self._prompts = prompt_loader
    self._cost_tracker = cost_tracker
    self._session_factory = session_factory
    self._max_concurrent_batch_workers = max_concurrent_batch_workers
    self._stale_batch_timeout_seconds = stale_batch_timeout_seconds
    self._model = model
```

- [ ] **Step 5: `start_batch` implementieren**

```python
# class NarrativeService:

async def start_batch(
    self,
    model_run_id: UUID,
    *,
    top_n: int = 20,
    language: Literal["de", "en"] = "de",
) -> MemoBatchJob:
    """Validiert Run, erstellt Job, spawned Background-Task, returnt sofort."""
    if language == "en":
        raise NotImplementedError(
            "EN-Memos sind in dieser Slice noch nicht implementiert. "
            "Bitte language='de' nutzen."
        )
    if not (1 <= top_n <= 100):
        raise ValueError(f"top_n must be 1..100, got {top_n}")

    # Run existiert?
    results = await self._run_repo.get_results(model_run_id)
    if results is None:
        raise LookupError(f"Run {model_run_id} not found")

    # Cost-Pre-Check
    estimated_usd = Decimal(top_n) * Decimal("0.025")
    await self._cost_tracker.check_cap(estimated_usd=estimated_usd)

    # Job anlegen
    job = MemoBatchJob(
        id=uuid4(),
        model_run_id=model_run_id,
        top_n=top_n,
        language=language,
        status="pending",
        failed_stock_ids=[],
        error_message=None,
        created_at=datetime.now(tz=UTC),
    )
    await self._batch_repo.save(job)

    # Background-Task spawnen (fire-and-forget)
    asyncio.create_task(self._execute_batch(job.id))

    return job
```

- [ ] **Step 6: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service_batch.py -v
```
Expected: 5 passed.

- [ ] **Step 7: DI-Wiring updaten** (damit der Service-Konstruktor mit den neuen Params noch instanziiert werden kann — Übergangs-Wiring vor Task 10)

In `backend/interfaces/rest/dependencies.py` `get_narrative_service` provisorisch:

```python
async def get_narrative_service(
    memo_repo: ResearchMemoRepository = Depends(get_research_memo_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    stock_repo: StockRepository = Depends(get_stock_repository),
    llm: LLMClient = Depends(get_llm_client),
    prompt_loader: PromptTemplateLoader = Depends(get_prompt_loader),
    cost_tracker: CostTracker = Depends(get_cost_tracker),
    settings: Settings = Depends(get_settings),
) -> NarrativeService:
    return NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        batch_repository=SQLAMemoBatchJobRepository(session_factory=get_session_factory()),
        llm_client=llm,
        prompt_loader=prompt_loader,
        cost_tracker=cost_tracker,
        session_factory=get_session_factory(),
        max_concurrent_batch_workers=settings.max_concurrent_batch_workers,
        stale_batch_timeout_seconds=settings.stale_batch_timeout_seconds,
    )
```

(Wird in Task 10 mit eigener `get_memo_batch_job_repository`-Factory sauberer.)

- [ ] **Step 8: Full Suite**

```bash
source .venv/bin/activate && ruff check backend/ && ruff format --check backend/ && mypy backend/ && python -m pytest backend/tests/unit -q
```
Expected: All clean, all unit tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/test_narrative_service_batch.py backend/config.py backend/interfaces/rest/dependencies.py
git commit -m "feat(narrative): NarrativeService.start_batch (build-step 7/12)

Validate Run exists, EN-Guard, top_n-Bounds, Cost-Pre-Check, Job
anlegen, Background-Task via asyncio.create_task fire-and-forget.

Settings erweitert: max_concurrent_batch_workers (3), stale_batch_timeout_seconds (600).

DI-Wiring provisorisch erweitert um batch_repository, cost_tracker,
session_factory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: NarrativeService — `_execute_batch` (Background-Worker)

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service_batch.py`

- [ ] **Step 1: Tests fuer `_execute_batch` schreiben**

```python
# backend/tests/unit/application/test_narrative_service_batch.py
# Erweitern:

class TestExecuteBatch:
    async def test_execute_batch_all_success_marks_complete(self, monkeypatch) -> None:
        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id, model_run_id=run_id, top_n=2, language="de",
            status="pending", failed_stock_ids=[],
            error_message=None, created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        run_repo = AsyncMock()
        run_repo.get_results = AsyncMock(return_value=[
            {"ticker": "A", "total_rank": 1, "stock_id": str(stock_ids[0])},
            {"ticker": "B", "total_rank": 2, "stock_id": str(stock_ids[1])},
        ])

        service = _make_service(batch_repo=batch_repo, run_repo=run_repo)
        # _generate_memo_isolated mocken — wir testen Worker-Loop, nicht Memo-Inhalt
        service._generate_memo_isolated = AsyncMock()  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        # save() mind. 2x gerufen: status=running, status=complete
        assert batch_repo.save.await_count >= 2
        last_save = batch_repo.save.await_args.args[0]
        assert last_save.status == "complete"
        assert last_save.failed_stock_ids == []

    async def test_execute_batch_partial_on_network_fail(self, monkeypatch) -> None:
        import anthropic

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id, model_run_id=run_id, top_n=2, language="de",
            status="pending", failed_stock_ids=[],
            error_message=None, created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        run_repo = AsyncMock()
        run_repo.get_results = AsyncMock(return_value=[
            {"ticker": "A", "total_rank": 1, "stock_id": str(stock_ids[0])},
            {"ticker": "B", "total_rank": 2, "stock_id": str(stock_ids[1])},
        ])

        service = _make_service(batch_repo=batch_repo, run_repo=run_repo)
        # Erster Stock: ok. Zweiter: APITimeoutError.
        async def _flaky(stock_id, *_args, **_kwargs):
            if stock_id == stock_ids[1]:
                raise anthropic.APITimeoutError(request=Mock())
            return Mock()

        service._generate_memo_isolated = AsyncMock(side_effect=_flaky)  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        last_save = batch_repo.save.await_args.args[0]
        assert last_save.status == "partial"
        assert stock_ids[1] in last_save.failed_stock_ids

    async def test_execute_batch_all_fail_marks_failed(self, monkeypatch) -> None:
        import anthropic

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id, model_run_id=run_id, top_n=2, language="de",
            status="pending", failed_stock_ids=[],
            error_message=None, created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        run_repo = AsyncMock()
        run_repo.get_results = AsyncMock(return_value=[
            {"ticker": "A", "total_rank": 1, "stock_id": str(stock_ids[0])},
            {"ticker": "B", "total_rank": 2, "stock_id": str(stock_ids[1])},
        ])

        service = _make_service(batch_repo=batch_repo, run_repo=run_repo)
        service._generate_memo_isolated = AsyncMock(  # type: ignore[method-assign]
            side_effect=anthropic.APIConnectionError(request=Mock())
        )

        await service._execute_batch(job_id)

        last_save = batch_repo.save.await_args.args[0]
        assert last_save.status == "failed"
        assert len(last_save.failed_stock_ids) == 2
```

- [ ] **Step 2: RED verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service_batch.py::TestExecuteBatch -v
```
Expected: Methode `_execute_batch` existiert noch nicht, Tests schlagen mit AttributeError fehl.

- [ ] **Step 3: `_execute_batch` implementieren**

```python
# class NarrativeService:

async def _execute_batch(self, job_id: UUID) -> None:
    """Background-Worker. Wird via asyncio.create_task gestartet.

    WICHTIG: Der Worker nutzt KEINE Service-eigenen Repos (die sind an
    die Request-Session des start_batch-Aufrufers gebunden, die laengst
    geschlossen ist). Stattdessen baut er pro parallelem Sub-Task eigene
    Sessions via session_factory (B1-Lehre).
    """
    import anthropic

    job = await self._batch_repo.get(job_id)
    if job is None:
        return  # Should not happen — job was just created

    # Status auf "running" setzen
    running = job.model_copy(
        update={"status": "running", "started_at": datetime.now(tz=UTC)}
    )
    await self._batch_repo.save(running)

    # Top-N stocks aus Run-Results bestimmen
    results = await self._run_repo.get_results(running.model_run_id)
    if results is None:
        # Sollte nicht passieren (start_batch hat schon validiert), aber defensiv
        failed = running.model_copy(
            update={
                "status": "failed",
                "completed_at": datetime.now(tz=UTC),
                "error_message": "Run results disappeared mid-batch",
            }
        )
        await self._batch_repo.save(failed)
        return

    # Sort by total_rank ASC, take top_n stock_ids
    sorted_results = sorted(results, key=lambda r: int(r["total_rank"]))
    top_stocks = sorted_results[: running.top_n]
    stock_ids: list[UUID] = [UUID(r["stock_id"]) for r in top_stocks]

    # Concurrency-Limit
    semaphore = asyncio.Semaphore(self._max_concurrent_batch_workers)
    failed_ids: list[UUID] = []

    async def _one(stock_id: UUID) -> tuple[str, UUID]:
        async with semaphore:
            # Eigene Session-Factory pro Worker (B1-Lehre)
            async with self._session_factory() as session:
                from backend.infrastructure.persistence.repositories.stock_repository import (
                    SQLAStockRepository,
                )
                from backend.infrastructure.persistence.repositories.ranking_run_repository import (
                    SQLARankingRunRepository,
                )

                isolated_stock_repo = SQLAStockRepository(session=session)
                isolated_run_repo = SQLARankingRunRepository(session=session)
                try:
                    await self._generate_memo_isolated(
                        stock_id,
                        running.model_run_id,
                        language=running.language,  # type: ignore[arg-type]
                        stock_repo=isolated_stock_repo,
                        run_repo=isolated_run_repo,
                    )
                    return ("ok", stock_id)
                except (
                    anthropic.APITimeoutError,
                    anthropic.APIConnectionError,
                ) as exc:
                    self._logger.warning(
                        "Batch %s memo failed for stock %s: %s",
                        job_id,
                        stock_id,
                        exc,
                    )
                    return ("failed", stock_id)

    results_per_stock = await asyncio.gather(*[_one(s) for s in stock_ids])
    failed_ids = [s for status, s in results_per_stock if status == "failed"]

    n_failed = len(failed_ids)
    if n_failed == 0:
        final_status: str = "complete"
    elif n_failed == len(stock_ids):
        final_status = "failed"
    else:
        final_status = "partial"

    final = running.model_copy(
        update={
            "status": final_status,
            "failed_stock_ids": failed_ids,
            "completed_at": datetime.now(tz=UTC),
        }
    )
    await self._batch_repo.save(final)
```

**Wichtig:** Importe von `SQLAStockRepository`/`SQLARankingRunRepository` *innerhalb* der `_one`-Funktion vermeiden Circular-Imports im application-Layer. Falls Style-Linter das anmeckert: Top-of-file mit `if TYPE_CHECKING` oder direkt am Anfang der `_execute_batch`-Methode importieren.

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service_batch.py::TestExecuteBatch -v
```
Expected: 3 passed.

- [ ] **Step 5: Logger im Service ergänzen**

Im Konstruktor:
```python
import logging
# ...
self._logger = logging.getLogger("backend.narrative_service")
```

- [ ] **Step 6: Lint + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && mypy backend/
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/test_narrative_service_batch.py
git commit -m "feat(narrative): _execute_batch Background-Worker (build-step 8/12)

Worker laeuft via asyncio.create_task. asyncio.Semaphore(N) bounds
Concurrency. Pro Sub-Task eigene Session via session_factory + isolated
Stock/Run-Repos (B1-Lehre — kein Sharing der Request-Session).

Status-Aggregation: complete (0 failed) | partial (1+ failed) | failed
(alle failed). APITimeoutError/APIConnectionError werden caught,
Stock-ID in failed_stock_ids. Schema-Validation-Fails landen weiterhin
als Error-Memos in DB (Single-Memo-Verhalten erhalten).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: NarrativeService — `get_batch_job` (mit Stale-Cleanup) + `list_memos_for_run`

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service_batch.py`

- [ ] **Step 1: Tests fuer Stale-Cleanup + list_memos_for_run schreiben**

```python
# backend/tests/unit/application/test_narrative_service_batch.py — TestGetBatchJob

class TestGetBatchJob:
    async def test_returns_none_for_unknown_id(self) -> None:
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=None)
        service = _make_service(batch_repo=batch_repo)

        result = await service.get_batch_job(uuid4())
        assert result is None

    async def test_returns_running_job_when_recent(self) -> None:
        recent_start = datetime.now(UTC)
        job = MemoBatchJob(
            id=uuid4(), model_run_id=uuid4(), top_n=20, language="de",
            status="running", failed_stock_ids=[],
            error_message=None, created_at=recent_start, started_at=recent_start,
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=job)
        service = _make_service(batch_repo=batch_repo)

        result = await service.get_batch_job(job.id)
        assert result is not None
        assert result.status == "running"
        # save() NICHT gerufen — kein cleanup nötig
        batch_repo.save.assert_not_awaited()

    async def test_marks_stale_running_as_failed(self) -> None:
        from datetime import timedelta

        old_start = datetime.now(UTC) - timedelta(seconds=700)  # > 600s timeout
        job = MemoBatchJob(
            id=uuid4(), model_run_id=uuid4(), top_n=20, language="de",
            status="running", failed_stock_ids=[],
            error_message=None, created_at=old_start, started_at=old_start,
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=job)
        service = _make_service(batch_repo=batch_repo)

        result = await service.get_batch_job(job.id)
        assert result is not None
        assert result.status == "failed"
        assert "stale" in (result.error_message or "").lower()
        batch_repo.save.assert_awaited_once()


class TestListMemosForRun:
    async def test_delegates_to_repo(self) -> None:
        memo_repo = AsyncMock()
        memo_repo.list_by_run = AsyncMock(return_value=[])
        service = _make_service(memo_repo=memo_repo)

        run_id = uuid4()
        await service.list_memos_for_run(run_id, language="de")
        memo_repo.list_by_run.assert_awaited_once_with(run_id, language="de")
```

- [ ] **Step 2: RED verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service_batch.py::TestGetBatchJob backend/tests/unit/application/test_narrative_service_batch.py::TestListMemosForRun -v
```
Expected: AttributeError für `get_batch_job` und `list_memos_for_run`.

- [ ] **Step 3: Methoden implementieren**

```python
# class NarrativeService:

async def get_batch_job(self, job_id: UUID) -> MemoBatchJob | None:
    """Laedt Job; bei status=running mit started_at>STALE_TIMEOUT macht
    lazy-cleanup (Stale-Job-Recovery nach Server-Crash)."""
    job = await self._batch_repo.get(job_id)
    if job is None:
        return None
    if job.status == "running" and job.started_at is not None:
        elapsed = (datetime.now(tz=UTC) - job.started_at).total_seconds()
        if elapsed > self._stale_batch_timeout_seconds:
            stale = job.model_copy(
                update={
                    "status": "failed",
                    "completed_at": datetime.now(tz=UTC),
                    "error_message": (
                        "Job stale — Server-Restart oder Crash waehrend Ausfuehrung"
                    ),
                }
            )
            await self._batch_repo.save(stale)
            return stale
    return job


async def list_memos_for_run(
    self,
    model_run_id: UUID,
    *,
    language: Literal["de", "en"] = "de",
) -> list[ResearchMemo]:
    """Helper fuer GET /jobs/{id}-Response: alle Memos fuer den Run + Sprache."""
    return await self._memo_repo.list_by_run(model_run_id, language=language)
```

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/unit/application/test_narrative_service_batch.py -v
```
Expected: alle Tests passed (5 + 3 + 3 + 1 = 12).

- [ ] **Step 5: Lint + Mypy**

```bash
source .venv/bin/activate && ruff check backend/ && mypy backend/
```
Expected: All clean.

- [ ] **Step 6: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/test_narrative_service_batch.py
git commit -m "feat(narrative): get_batch_job mit Stale-Cleanup + list_memos_for_run (build-step 9/12)

get_batch_job macht lazy-cleanup: running-Job mit started_at >
stale_batch_timeout_seconds wird zu 'failed' gemarkt mit error_message.

list_memos_for_run delegiert an memo_repo.list_by_run — Helper fuer
die GET-Response-Erstellung.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: REST-Endpoints + Pydantic Request/Response-Schemas + DI-Wiring

**Files:**
- Create: `backend/interfaces/rest/schemas/memo_batch.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Modify: `backend/interfaces/rest/routers/memos.py`
- Test: `backend/tests/integration/test_memo_batch_endpoint.py`

- [ ] **Step 1: Pydantic-Schemas erstellen**

```python
# backend/interfaces/rest/schemas/memo_batch.py
"""Request/Response-Schemas fuer Multi-Memo Batch-Endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BatchRequest(BaseModel):
    model_run_id: UUID
    top_n: int = Field(20, ge=1, le=100)
    language: Literal["de", "en"] = "de"


class BatchProgress(BaseModel):
    expected: int
    completed: int
    failed: int


class BatchMemoSummary(BaseModel):
    stock_id: UUID
    ticker: str
    one_liner: str
    is_error: bool


class BatchJobResponse(BaseModel):
    job_id: UUID
    model_run_id: UUID
    top_n: int
    language: Literal["de", "en"]
    status: Literal["pending", "running", "complete", "partial", "failed"]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    progress: BatchProgress
    failed_stock_ids: list[UUID]
    error_message: str | None
    memos: list[BatchMemoSummary]


class BatchJobAcceptedResponse(BaseModel):
    """202-Accepted-Response — schlanker als BatchJobResponse."""

    job_id: UUID
    model_run_id: UUID
    top_n: int
    language: Literal["de", "en"]
    status: Literal["pending"]
    created_at: datetime
```

- [ ] **Step 2: DI-Wiring**

```python
# backend/interfaces/rest/dependencies.py — neue Factory:

async def get_memo_batch_job_repository() -> MemoBatchJobRepository:
    """Eigene Session-Factory analog get_research_memo_repository."""
    return SQLAMemoBatchJobRepository(session_factory=get_session_factory())
```

`get_narrative_service` so anpassen dass es `get_memo_batch_job_repository` als `Depends(...)` nutzt (statt direkt zu instantiieren wie in Task 7-Step-7).

- [ ] **Step 3: Integration-Tests fuer Endpoints schreiben**

```python
# backend/tests/integration/test_memo_batch_endpoint.py
"""Integration-Tests fuer /api/v1/memos/batch + /jobs/{id}."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_narrative_service

pytestmark = pytest.mark.integration


def _make_pending_job(run_id=None) -> MemoBatchJob:
    return MemoBatchJob(
        id=uuid4(),
        model_run_id=run_id or uuid4(),
        top_n=20,
        language="de",
        status="pending",
        failed_stock_ids=[],
        error_message=None,
        created_at=datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def app_with_mock_service() -> Any:
    app = create_app()
    mock_service = AsyncMock(spec=NarrativeService)
    app.dependency_overrides[get_narrative_service] = lambda: mock_service
    yield app, mock_service
    app.dependency_overrides.clear()


def test_post_batch_returns_202(app_with_mock_service):
    app, service = app_with_mock_service
    job = _make_pending_job()
    service.start_batch = AsyncMock(return_value=job)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(job.model_run_id), "top_n": 20},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert UUID(body["job_id"]) == job.id


def test_post_batch_returns_404_run_missing(app_with_mock_service):
    app, service = app_with_mock_service
    service.start_batch = AsyncMock(side_effect=LookupError("Run x not found"))

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(uuid4()), "top_n": 20},
        )

    assert resp.status_code == 404


def test_post_batch_returns_402_budget_exceeded(app_with_mock_service):
    from backend.domain.errors import BudgetCapExceededError

    app, service = app_with_mock_service
    service.start_batch = AsyncMock(side_effect=BudgetCapExceededError("over"))

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(uuid4()), "top_n": 20},
        )

    assert resp.status_code == 402


def test_get_job_returns_404_unknown(app_with_mock_service):
    app, service = app_with_mock_service
    service.get_batch_job = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{uuid4()}")
    assert resp.status_code == 404


def test_get_job_returns_status_and_progress(app_with_mock_service):
    app, service = app_with_mock_service
    job = _make_pending_job()
    job_running = job.model_copy(update={"status": "running", "started_at": datetime.now(UTC)})
    service.get_batch_job = AsyncMock(return_value=job_running)
    service.list_memos_for_run = AsyncMock(return_value=[])  # noch keine memos

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{job.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["progress"]["expected"] == 20
    assert body["progress"]["completed"] == 0
    assert body["progress"]["failed"] == 0
```

- [ ] **Step 4: Router erweitern**

```python
# backend/interfaces/rest/routers/memos.py — neue Endpoints:

from backend.domain.errors import BudgetCapExceededError
from backend.interfaces.rest.schemas.memo_batch import (
    BatchJobAcceptedResponse,
    BatchJobResponse,
    BatchMemoSummary,
    BatchProgress,
    BatchRequest,
)


@router.post(
    "/batch",
    response_model=BatchJobAcceptedResponse,
    status_code=202,
)
async def post_batch(
    body: BatchRequest,
    service: NarrativeService = Depends(get_narrative_service),
) -> BatchJobAcceptedResponse:
    try:
        job = await service.start_batch(
            body.model_run_id,
            top_n=body.top_n,
            language=body.language,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BudgetCapExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    return BatchJobAcceptedResponse(
        job_id=job.id,
        model_run_id=job.model_run_id,
        top_n=job.top_n,
        language=job.language,
        status="pending",
        created_at=job.created_at,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=BatchJobResponse,
)
async def get_job(
    job_id: UUID,
    service: NarrativeService = Depends(get_narrative_service),
) -> BatchJobResponse:
    job = await service.get_batch_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    memos = await service.list_memos_for_run(job.model_run_id, language=job.language)
    memo_summaries = [
        BatchMemoSummary(
            stock_id=m.stock_id,
            ticker="",  # Wird in Task 11 mit Stock-Lookup erweitert
            one_liner=m.one_liner,
            is_error=(m.model_version == "error-fallback"),
        )
        for m in memos
    ]

    return BatchJobResponse(
        job_id=job.id,
        model_run_id=job.model_run_id,
        top_n=job.top_n,
        language=job.language,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress=BatchProgress(
            expected=job.top_n,
            completed=len(memos),
            failed=len(job.failed_stock_ids),
        ),
        failed_stock_ids=job.failed_stock_ids,
        error_message=job.error_message,
        memos=memo_summaries,
    )
```

**Hinweis:** `BatchMemoSummary.ticker=""` ist Placeholder — in Task 11 wird ein Stock-Lookup hinzugefuegt damit Frontend echte Tickers sieht. Für Task 10 reicht der leere String, damit Endpoint funktioniert.

- [ ] **Step 5: Tests laufen**

```bash
source .venv/bin/activate && python -m pytest backend/tests/integration/test_memo_batch_endpoint.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Lint + Mypy + Full Suite**

```bash
source .venv/bin/activate && ruff check backend/ && ruff format --check backend/ && mypy backend/ && python -m pytest backend/tests -q
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add backend/interfaces/rest/schemas/memo_batch.py backend/interfaces/rest/dependencies.py backend/interfaces/rest/routers/memos.py backend/tests/integration/test_memo_batch_endpoint.py
git commit -m "feat(rest): POST /memos/batch + GET /memos/jobs/{id} (build-step 10/12)

Pydantic Request/Response-Schemas in interfaces/rest/schemas/memo_batch.py.
Router-Endpoints mit Error-Mapping (404 für Run/Job missing, 402 für
Budget-Cap, 501 fuer EN). DI-Wiring um get_memo_batch_job_repository
ergaenzt.

GET /jobs/{id} buildet Response aus Job + list_memos_for_run.
BatchMemoSummary.ticker bleibt leer — Stock-Ticker-Lookup in Task 11.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: E2E-Integration-Test + Ticker-Lookup im Response

**Files:**
- Modify: `backend/interfaces/rest/routers/memos.py` (Ticker-Lookup)
- Modify: `backend/application/services/narrative_service.py` (helper für ticker-lookup)
- Test: `backend/tests/integration/test_memo_batch_full_flow.py` (NEU)

- [ ] **Step 1: Service-Helper für Stock-Lookup-Map**

```python
# class NarrativeService:

async def get_stock_ticker_map(
    self, stock_ids: list[UUID]
) -> dict[UUID, str]:
    """Lookup-Map stock_id -> ticker, fuer GET /jobs/{id}-Response."""
    out: dict[UUID, str] = {}
    for sid in stock_ids:
        stock = await self._stock_repo.get(sid)
        if stock is not None:
            out[sid] = stock.ticker
    return out
```

(Optional: später optimieren mit `list_by_ids`-Bulk-Query, jetzt YAGNI.)

- [ ] **Step 2: Router erweitern um Ticker-Map**

```python
# In get_job:
stock_ids = [m.stock_id for m in memos]
ticker_map = await service.get_stock_ticker_map(stock_ids)

memo_summaries = [
    BatchMemoSummary(
        stock_id=m.stock_id,
        ticker=ticker_map.get(m.stock_id, ""),
        one_liner=m.one_liner,
        is_error=(m.model_version == "error-fallback"),
    )
    for m in memos
]
```

- [ ] **Step 3: E2E-Test schreiben**

```python
# backend/tests/integration/test_memo_batch_full_flow.py
"""E2E-Integration-Test: POST /batch -> Polling -> Memos in DB."""

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.interfaces.rest.app import create_app

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_batch_top_3_full_flow(integration_db_with_stocks_and_run, stub_anthropic):
    """POST /batch top_n=3 -> Polling bis status=complete -> 3 memos in DB."""
    app = create_app()
    # stub_anthropic-Override + integration-DB

    with TestClient(app) as client:
        # POST /batch
        resp = client.post(
            "/api/v1/memos/batch",
            json={
                "model_run_id": str(integration_db_with_stocks_and_run.run_id),
                "top_n": 3,
                "language": "de",
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        # Polling bis status terminal (max 30s)
        for _ in range(30):
            await asyncio.sleep(1)
            poll = client.get(f"/api/v1/memos/jobs/{job_id}")
            assert poll.status_code == 200
            body = poll.json()
            if body["status"] in ("complete", "partial", "failed"):
                break
        else:
            pytest.fail("Job did not finish in 30s")

        # Final assertions
        assert body["status"] == "complete"
        assert body["progress"]["completed"] == 3
        assert body["progress"]["failed"] == 0
        assert len(body["memos"]) == 3
        for memo in body["memos"]:
            assert memo["ticker"] != ""  # Ticker-Lookup funktioniert
            assert memo["is_error"] is False
```

**Fixture-Hinweis:** `integration_db_with_stocks_and_run` muss 3+ Stocks + 1 RankingRun + 1 RankingRunResult mit stock_id-Referenzen seeden. Pattern aus `test_narrative_service_integration.py` reusen.

- [ ] **Step 4: GREEN verifizieren**

```bash
source .venv/bin/activate && python -m pytest backend/tests/integration/test_memo_batch_full_flow.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Lint + Mypy + Full Suite**

```bash
source .venv/bin/activate && ruff check backend/ && ruff format --check backend/ && mypy backend/ && python -m pytest backend/tests -q
```
Expected: All clean, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/application/services/narrative_service.py backend/interfaces/rest/routers/memos.py backend/tests/integration/test_memo_batch_full_flow.py
git commit -m "feat(rest): Ticker-Lookup in BatchJobResponse + E2E-Test (build-step 11/12)

NarrativeService.get_stock_ticker_map als helper fuer den Router.
Naive 1-Stock-per-call-Implementation (kein Bulk-Query, YAGNI).

E2E-Test: POST /batch top_n=3 -> Polling bis complete -> assert 3 Memos
mit Tickers in Response. Nutzt StubAnthropic + PG.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Real-API-Smoke-Skript + AI-USAGE + Spec §11.1

**Files:**
- Create: `scripts/smoke_narrative_batch_real_api.py`
- Modify: `docs/AI-USAGE.md`
- Modify: `docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md` (§11.1)

- [ ] **Step 1: Smoke-Skript schreiben**

```python
# scripts/smoke_narrative_batch_real_api.py
"""Smoke-Test: Multi-Memo Batch gegen echte Anthropic-API.

Verifiziert Acceptance §10:
- POST /batch top_n=3 (kleiner Batch zur Cost-Kontrolle, ~$0.10)
- Polling bis complete
- cache_read_input_tokens > 0 ab Memo 2 verifiziert via CostLog
- 3 Memos in DB

Vorbedingung: docker-compose up + seed_demo_universe.py + Run angelegt
mit mind. 3 Stocks. ANTHROPIC_API_KEY in .env.

Ausfuehrung:
    python scripts/smoke_narrative_batch_real_api.py <model_run_id>
"""

import asyncio
import sys
import time
from uuid import UUID

import httpx


async def main(run_id: str) -> None:
    base_url = "http://localhost:8000/api/v1"
    async with httpx.AsyncClient() as client:
        # POST /batch
        print(f"POST /memos/batch run_id={run_id} top_n=3 ...")
        resp = await client.post(
            f"{base_url}/memos/batch",
            json={"model_run_id": run_id, "top_n": 3, "language": "de"},
        )
        resp.raise_for_status()
        job = resp.json()
        job_id = job["job_id"]
        print(f"  Job created: {job_id} (status={job['status']})")

        # Polling
        print("Polling /jobs/{job_id} every 2s ...")
        start = time.perf_counter()
        for i in range(60):
            await asyncio.sleep(2)
            poll = await client.get(f"{base_url}/memos/jobs/{job_id}")
            poll.raise_for_status()
            body = poll.json()
            elapsed = time.perf_counter() - start
            print(
                f"  [{elapsed:.1f}s] status={body['status']} "
                f"progress={body['progress']['completed']}/{body['progress']['expected']} "
                f"failed={body['progress']['failed']}"
            )
            if body["status"] in ("complete", "partial", "failed"):
                break
        else:
            print("FAIL: Job did not finish in 120s")
            sys.exit(1)

        # Final report
        print(f"\nFinal: status={body['status']}")
        print(f"Memos generated: {len(body['memos'])}")
        for m in body["memos"]:
            print(f"  - {m['ticker']}: {m['one_liner']}")
        if body["failed_stock_ids"]:
            print(f"\nFailed stocks: {body['failed_stock_ids']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/smoke_narrative_batch_real_api.py <model_run_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
```

- [ ] **Step 2: Smoke ausfuehren** (Sheyla manuell auf lokaler Umgebung)

```bash
source .venv/bin/activate && python scripts/smoke_narrative_batch_real_api.py <existing_run_id>
```

Expected:
- POST returnt 202 + job_id
- Polling zeigt running → complete in 5-15s (top_n=3, ~3s/memo)
- 3 Memos mit Tickers + one_liner-Strings
- 0 failed
- Cost-Log zeigt 1 cache_create + 2 cache_read Eintraege

- [ ] **Step 3: AI-USAGE-Eintrag schreiben**

Eintrag im Stil der bisherigen ergänzen, mit:
- Reflexion über Plan-Code-Drifts (falls vorhanden)
- Was gut/schlecht lief beim Async-Job-Pattern
- Lehre für künftige Long-Running-Tasks

Konkretes Format wie bei PR #64 / Foundation: Was gut lief / Was nicht klappte / Lektion / Token-Kosten.

- [ ] **Step 4: Spec §11.1 ergänzen** (falls Drifts gefunden)

Falls bei Implementation Plan-Code-Drifts entdeckt wurden, in `docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md` §11.1 dokumentieren — analog Single-Memo-Spec §11.1.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_narrative_batch_real_api.py docs/AI-USAGE.md docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md
git commit -m "docs: Smoke-Skript + AI-USAGE + Spec-Drifts (build-step 12/12)

Smoke-Skript fuer Real-API-Verifikation mit Polling-Pattern. AI-USAGE
mit Reflexion ueber Async-Job-Pattern als erstes Long-Running-Pattern
im Repo. Spec §11.1 mit Plan-Code-Drifts (falls vorhanden).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Acceptance Checklist

- [ ] Tasks 1-12 sequenziell durchgelaufen
- [ ] Volle Suite grün (`pytest backend/tests`)
- [ ] Coverage ≥ 90% auf neuen Code
- [ ] mypy strict + ruff format/check clean
- [ ] Real-API-Smoke einmal manuell verifiziert (Task 12)
- [ ] AI-USAGE-Eintrag committed
- [ ] PR-Body mit Spec-Link + Test-Resultaten
- [ ] Re-Review-Request nach Push

---

## Self-Review (post-plan)

**Spec-Coverage:** Alle Sektionen der Spec sind durch Tasks abgedeckt:
- §3 Architektur → Tasks 1-3 (Domain), 4-5 (Persistence), 7-9 (Service), 10-11 (REST)
- §4 Domain → Task 1 (Entity) + Task 3 (ORM/Migration)
- §5 Service-API → Tasks 6-9 (start_batch, _execute_batch, get_batch_job, list_memos_for_run, _generate_memo_isolated)
- §6 REST → Tasks 10-11 (Endpoints + E2E)
- §7 Cost & Caching → integriert in Tasks 7 (Pre-Check), 12 (Smoke verifiziert Cache)
- §8 Error-Handling → Tasks 7 (Pre-Job), 8 (Per-Memo), 9 (Stale)
- §9 Test-Strategie → Tests in jedem Task, E2E in Task 11

**Placeholder-Scan:** Keine "TBD"/"TODO" — alle Steps haben konkreten Code/Commands.

**Type-Konsistenz:** `MemoBatchJob` und `MemoBatchJobRepository` verwendet einheitlich. `_generate_memo_isolated`-Signatur konsistent zwischen Task 6 (Definition) und Task 8 (Verwendung).

**Worker-Repos-Pattern:** Task 8 importiert SQLAStockRepository/SQLARankingRunRepository inline. Falls ruff/import-style das anmeckert: Top-of-file-Imports oder TYPE_CHECKING-Variante als Plan-Drift in §11.1 dokumentieren.

**Bekannte Vereinfachungen:**
- `get_stock_ticker_map` (Task 11) ist N+1-Query, nicht Bulk. YAGNI — bei N=20 ist das ~50ms pro GET, vernachlässigbar. Folge-PR wenn die Tabelle in den Tausenden ist.
- Cost-Pre-Check nutzt fixe `$0.025/memo`-Schätzung. Realistisch ist's ~$0.016 mit Cache, ~$0.027 ohne. 25 cents ist konservativer Worst-Case → Cap-Schwelle leck-sicherer.

---

## Execution Handoff

**Plan complete und auf `spec/narrative-multi-memo-batch` committed.**

Zwei Execution-Optionen:

**1. Parallele Agent-Ausführung (empfohlen)** — Pro Task ein frischer Agent, zweistufiger Review zwischen Tasks, schnelle Iteration. Pattern wie bei Single-Memo-Slice und Foundation.

**2. Inline Execution** — Sheyla + Claude im selben Session-Kontext, Batch-Execution mit Checkpoints für Review.

Welche?
