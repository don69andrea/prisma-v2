# Narrative-Followups Bundle (#66 + #67) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disziplinierung der Narrative-Engine-Schnittstelle: (a) Score=1/rank-Hallucination aus Prompt-Pfad entfernen (#66), (b) `is_error` als echtes Entity-Feld mit Migration + Backfill statt String-Match (#67).

**Architecture:** Zwei thematisch zusammengehörige Folge-Fixes als ein PR. #66 ändert Helper + 2 Templates (DE + EN nach #116-Merge). #67 fügt Entity-Feld + ORM-Spalte + Migration 0009 + Service-Bridge-Inference (`schema.model_version == ERROR_FALLBACK_MODEL_VERSION`) hinzu und entkernt den Router. Sentinel `ERROR_FALLBACK_MODEL_VERSION` bleibt als zusätzliche Markierung.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic 2, Jinja2 (Templates), pytest + pytest-asyncio, ruff + mypy strict.

**Spec:** `docs/specs/2026-05-14-narrative-followups-66-67.md`

---

## Pre-Execution Check

**REQUIRED before starting Task 1:** Verify PR #116 (EN-Template) is merged on main.

```bash
gh pr view 116 --json state
# Expected: {"state":"MERGED"}

git checkout main
git pull --ff-only
ls backend/infrastructure/llm/prompts/
# Expected: narrative_user.de.md.j2, narrative_user.en.md.j2,
#           narrative_system.de.md.j2, narrative_system.en.md.j2
```

Wenn `narrative_user.md.j2` (ohne `.de`) noch existiert → #116 ist nicht gemerged, **nicht starten**.

Branch von aktuellem main neu rebasen:
```bash
git checkout feat/narrative-followups-66-67
git rebase origin/main
```

---

## File Structure

**Files created (1):**
- `backend/alembic/versions/0009_add_is_error_to_research_memos.py` — Migration: ADD COLUMN + Backfill

**Files modified (~10):**
- `backend/domain/entities/research_memo.py` — `is_error: bool = False` Feld
- `backend/infrastructure/persistence/models/research_memo.py` — ORM-Spalte
- `backend/infrastructure/persistence/repositories/research_memo_repository.py` — save() + _orm_to_entity()
- `backend/application/services/narrative_service.py` — `_build_memo_entity` setzt is_error, `_rankings_for_template` ohne score
- `backend/interfaces/rest/routers/memos.py` — String-Match entfernen, direkt `memo.is_error` lesen
- `backend/infrastructure/llm/prompts/narrative_user.de.md.j2` — Score-Spalte raus
- `backend/infrastructure/llm/prompts/narrative_user.en.md.j2` — Score-Spalte raus
- `backend/infrastructure/llm/prompts/narrative_system.de.md.j2` — Score-Few-Shot raus
- `backend/infrastructure/llm/prompts/narrative_system.en.md.j2` — Score-Few-Shot raus
- `backend/tests/fixtures/prompts/expected_user_prompt.de.md` + `.en.md` — Snapshots ohne Score
- `backend/tests/unit/infrastructure/test_prompt_loader.py` — Test-Input ohne `score`-Keys
- `docs/AI-USAGE.md` — Slice-Reflexion

---

### Task 1: Entity-Feld `is_error: bool` auf ResearchMemo

**Files:**
- Modify: `backend/domain/entities/research_memo.py`
- Test: `backend/tests/unit/domain/entities/test_research_memo.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/unit/domain/entities/test_research_memo.py`:

```python
class TestResearchMemoIsError:
    """is_error-Feld: persistierte Markierung statt Router-String-Match (Issue #67)."""

    def _valid_kwargs(self) -> dict[str, Any]:
        return {
            "id": uuid4(),
            "stock_id": uuid4(),
            "model_run_id": uuid4(),
            "created_at": datetime.now(tz=UTC),
            "one_liner": "Test-Memo",
            "ranking_interpretation": "x" * 100,
            "sweet_spot": False,
            "sweet_spot_explanation": None,
            "contradictions": [],
            "key_strengths": ["s1"],
            "key_risks": ["r1"],
            "confidence": "low",
            "model_version": "claude-sonnet-4-6",
        }

    def test_default_is_error_is_false(self) -> None:
        memo = ResearchMemo(**self._valid_kwargs())
        assert memo.is_error is False

    def test_explicit_is_error_true(self) -> None:
        memo = ResearchMemo(**self._valid_kwargs(), is_error=True)
        assert memo.is_error is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/unit/domain/entities/test_research_memo.py::TestResearchMemoIsError -v
```

Expected: FAIL — `AttributeError` or `ValidationError` because `is_error` is unknown field.

- [ ] **Step 3: Add field to entity**

In `backend/domain/entities/research_memo.py`, add field to `ResearchMemo` class after `model_version`:

```python
    model_version: str = Field(..., max_length=64)
    is_error: bool = Field(default=False)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest backend/tests/unit/domain/entities/test_research_memo.py -v
```

Expected: PASS, alle bestehenden Tests bleiben grün.

- [ ] **Step 5: Commit**

```bash
git add backend/domain/entities/research_memo.py backend/tests/unit/domain/entities/test_research_memo.py
git commit -m "feat(narrative): is_error-Feld auf ResearchMemo-Entity (#67)

Default False, in Service-Bridge gesetzt anhand model_version-Sentinel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migration 0009 — ADD COLUMN + Backfill

**Files:**
- Create: `backend/alembic/versions/0009_add_is_error_to_research_memos.py`

**Note:** Migration 0008 ist bereits durch RAG-Slice belegt (`0008_enable_pgvector_and_create_embeddings.py`). Wir nehmen 0009.

- [ ] **Step 1: Create migration file**

Create `backend/alembic/versions/0009_add_is_error_to_research_memos.py`:

```python
"""add is_error column to research_memos

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-14

Issue #67: Router-Logik erbte is_error per String-Match aus one_liner. Mit
echtem is_error-Feld auf der Entity (PR-Bundle #66+#67) braucht es die
DB-Spalte. Backfill setzt historische Error-Memos (model_version =
'error-fallback') auf is_error=True.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_memos",
        sa.Column(
            "is_error",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Backfill: bisherige Error-Memos anhand des Sentinels markieren
    op.execute(
        "UPDATE research_memos SET is_error = true "
        "WHERE model_version = 'error-fallback'"
    )


def downgrade() -> None:
    op.drop_column("research_memos", "is_error")
```

- [ ] **Step 2: Verify Alembic discovers the migration**

```bash
cd backend && uv run alembic heads
```

Expected output: `0009 (head)` — single head.

- [ ] **Step 3: Run upgrade against local docker-compose Postgres**

```bash
# Ensure docker-compose db is up
docker-compose up -d db
# Optional: seed an error-fallback row before upgrade to verify backfill
psql -h localhost -p 5432 -U prisma -d prisma -c \
  "SELECT id, model_version FROM research_memos WHERE model_version='error-fallback' LIMIT 5;"
# Run migration
cd backend && uv run alembic upgrade head
```

Expected: kein Error, `is_error` column exists.

- [ ] **Step 4: Manually verify backfill**

```bash
psql -h localhost -p 5432 -U prisma -d prisma -c \
  "SELECT model_version, is_error, count(*) FROM research_memos GROUP BY 1, 2;"
```

Expected: rows mit `model_version='error-fallback'` haben `is_error=true`, alle anderen `is_error=false`.

Wenn keine Error-Rows existieren: leeres Resultat ist OK, Migration ist trotzdem valid.

- [ ] **Step 5: Run downgrade + upgrade to verify reversibility**

```bash
cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head
```

Expected: beide Schritte ohne Fehler.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0009_add_is_error_to_research_memos.py
git commit -m "feat(persistence): Migration 0009 add is_error to research_memos (#67)

ADD COLUMN is_error BOOLEAN NOT NULL DEFAULT false + Backfill auf
model_version='error-fallback'. Reversibel via downgrade DROP COLUMN.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: ORM-Spalte + Repository-Mapping

**Files:**
- Modify: `backend/infrastructure/persistence/models/research_memo.py`
- Modify: `backend/infrastructure/persistence/repositories/research_memo_repository.py`
- Test: `backend/tests/integration/persistence/test_research_memo_repository.py`

- [ ] **Step 1: Write failing roundtrip test**

Append a new test method to the existing test class in `backend/tests/integration/persistence/test_research_memo_repository.py`:

```python
async def test_save_and_load_preserves_is_error(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_stock_and_run: tuple[UUID, UUID],
) -> None:
    """is_error wird persistiert und beim Load wieder gesetzt (#67)."""
    stock_id, run_id = seeded_stock_and_run
    repo = SQLAResearchMemoRepository(session_factory)
    memo = ResearchMemo(
        id=uuid4(),
        stock_id=stock_id,
        model_run_id=run_id,
        created_at=datetime.now(tz=UTC),
        one_liner="Test-Error-Memo",
        ranking_interpretation="x" * 100,
        sweet_spot=False,
        sweet_spot_explanation=None,
        contradictions=[],
        key_strengths=["—"],
        key_risks=["—"],
        confidence="low",
        model_version="error-fallback",
        is_error=True,
    )
    await repo.save(memo)
    loaded = await repo.get(stock_id=stock_id, model_run_id=run_id, language="de")
    assert loaded is not None
    assert loaded.is_error is True
```

**Note:** Falls die Fixture `seeded_stock_and_run` nicht existiert oder anders heißt, **erst die existierenden Tests lesen** und das gleiche Fixture-Pattern verwenden. NICHT neue Fixture erfinden.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/integration/persistence/test_research_memo_repository.py::test_save_and_load_preserves_is_error -v
```

Expected: FAIL — entweder `TypeError: pg_insert got unexpected keyword 'is_error'` oder loaded.is_error ist nicht gesetzt.

- [ ] **Step 3: Add ORM column**

In `backend/infrastructure/persistence/models/research_memo.py`, add new column after `model_version` (around line 61):

```python
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
```

Make sure `sa` is imported (it should be via `import sqlalchemy as sa`; if not, add).

- [ ] **Step 4: Update repository save() — values + on_conflict_do_update set_**

In `backend/infrastructure/persistence/repositories/research_memo_repository.py`, modify the `save()` method.

In `.values(...)` block (around line 32), add after `model_version`:
```python
                    model_version=memo.model_version,
                    is_error=memo.is_error,
```

In `.on_conflict_do_update(... set_={...})` block (around line 50), add:
```python
                        "model_version": memo.model_version,
                        "is_error": memo.is_error,
```

- [ ] **Step 5: Update `_orm_to_entity()` mapping**

In the same file, in function `_orm_to_entity` (line 102), add `is_error` to the constructor:

```python
        model_version=row.model_version,
        is_error=row.is_error,
    )
```

- [ ] **Step 6: Run roundtrip test to verify it passes**

```bash
uv run pytest backend/tests/integration/persistence/test_research_memo_repository.py -v
```

Expected: all PASS including new test.

- [ ] **Step 7: Commit**

```bash
git add backend/infrastructure/persistence/models/research_memo.py \
        backend/infrastructure/persistence/repositories/research_memo_repository.py \
        backend/tests/integration/persistence/test_research_memo_repository.py
git commit -m "feat(persistence): ORM-Spalte is_error + Roundtrip-Mapping (#67)

ResearchMemoORM bekommt is_error-Column; save() schreibt sie auf INSERT
und UPSERT-set_; _orm_to_entity reicht durch zur Entity.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Service-Bridge `_build_memo_entity` setzt is_error

**Files:**
- Modify: `backend/application/services/narrative_service.py` (function `_build_memo_entity` at line 641)
- Test: `backend/tests/unit/application/test_narrative_service.py`

- [ ] **Step 1: Write failing unit test**

Append to `backend/tests/unit/application/test_narrative_service.py`:

```python
def test_build_memo_entity_marks_error_fallback_as_is_error() -> None:
    """_build_memo_entity setzt is_error=True wenn schema.model_version ist
    der Error-Sentinel — Single-Point-of-Truth statt Router-String-Match (#67)."""
    from backend.application.services.narrative_service import NarrativeService
    from backend.domain.entities.research_memo import ERROR_FALLBACK_MODEL_VERSION
    from backend.domain.schemas.research_memo_schema import ResearchMemoSchema

    error_schema = ResearchMemoSchema(
        ticker="NESN",
        total_rank=1,
        one_liner="Memo-Generierung fehlgeschlagen",
        ranking_interpretation="x" * 100,
        sweet_spot=False,
        sweet_spot_explanation=None,
        contradictions=[],
        key_strengths=["—"],
        key_risks=["—"],
        confidence="low",
        generated_at=datetime.now(tz=UTC),
        model_version=ERROR_FALLBACK_MODEL_VERSION,
    )
    # NarrativeService instance not needed for static-shape call — instantiate minimal mock
    # if dependencies are required; otherwise extract bridge to module-level if it doesn't
    # need `self`. (Currently it doesn't reference self — see narrative_service.py:641-664.)
    entity = NarrativeService._build_memo_entity(
        None,  # type: ignore[arg-type]
        error_schema,
        stock_id=uuid4(),
        model_run_id=uuid4(),
        language="de",
    )
    assert entity.is_error is True


def test_build_memo_entity_normal_path_is_not_error() -> None:
    """Normales Memo: is_error=False."""
    from backend.application.services.narrative_service import NarrativeService
    from backend.domain.schemas.research_memo_schema import ResearchMemoSchema

    normal_schema = ResearchMemoSchema(
        ticker="NESN",
        total_rank=1,
        one_liner="NESN — Top-Quintil-Performer",
        ranking_interpretation="x" * 100,
        sweet_spot=True,
        sweet_spot_explanation="x" * 50,
        contradictions=[],
        key_strengths=["s1"],
        key_risks=["r1"],
        confidence="high",
        generated_at=datetime.now(tz=UTC),
        model_version="claude-sonnet-4-6",
    )
    entity = NarrativeService._build_memo_entity(
        None,  # type: ignore[arg-type]
        normal_schema,
        stock_id=uuid4(),
        model_run_id=uuid4(),
        language="de",
    )
    assert entity.is_error is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py::test_build_memo_entity_marks_error_fallback_as_is_error backend/tests/unit/application/test_narrative_service.py::test_build_memo_entity_normal_path_is_not_error -v
```

Expected: FAIL — `is_error` not derived; both tests show is_error=False (or schema rejection).

- [ ] **Step 3: Modify `_build_memo_entity` in narrative_service.py:641**

Locate the function (line 641-664). Add `is_error` derivation in the `ResearchMemo(...)` call:

```python
        return ResearchMemo(
            id=uuid4(),
            stock_id=stock_id,
            model_run_id=model_run_id,
            language=language,
            created_at=datetime.now(tz=UTC),
            one_liner=schema.one_liner,
            ranking_interpretation=schema.ranking_interpretation,
            sweet_spot=schema.sweet_spot,
            sweet_spot_explanation=schema.sweet_spot_explanation,
            contradictions=list(schema.contradictions),
            key_strengths=list(schema.key_strengths),
            key_risks=list(schema.key_risks),
            confidence=schema.confidence,
            model_version=schema.model_version,
            is_error=(schema.model_version == ERROR_FALLBACK_MODEL_VERSION),
        )
```

Ensure `ERROR_FALLBACK_MODEL_VERSION` is imported at the top of the file (likely already is — verify).

- [ ] **Step 4: Run all unit tests to verify they pass**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v
```

Expected: alle PASS, neue + bestehende.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/narrative_service.py \
        backend/tests/unit/application/test_narrative_service.py
git commit -m "feat(narrative): _build_memo_entity setzt is_error aus model_version (#67)

Single-Point-of-Truth für is_error: an der Schema→Entity-Brücke statt
verteilter String-Matches. ERROR_FALLBACK_MODEL_VERSION bleibt als
zusätzliche visuelle Markierung in DB-Logs erhalten.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Router-Simplification — String-Match raus

**Files:**
- Modify: `backend/interfaces/rest/routers/memos.py` (lines 61-82 + 185)
- Test: `backend/tests/integration/test_memos_endpoint.py`

- [ ] **Step 1: Write failing integration test**

Append to `backend/tests/integration/test_memos_endpoint.py`:

```python
async def test_memo_response_is_error_uses_entity_field_not_string_match(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    seeded_stock_and_run: tuple[UUID, UUID],
) -> None:
    """Router liest memo.is_error direkt — kein String-Match auf one_liner.

    Edge-Case (Issue #67): wenn jemand manuell eine Row mit
    model_version='claude-sonnet-4-6' und is_error=True einfügt (Hypothetisch,
    aber genau die Robustheit die wir wollen), MUSS die API is_error=True
    zurückgeben. String-Match auf 'Memo-Generierung fehlgeschlagen' würde
    fehlschlagen.
    """
    stock_id, run_id = seeded_stock_and_run
    repo = SQLAResearchMemoRepository(session_factory)
    memo = ResearchMemo(
        id=uuid4(),
        stock_id=stock_id,
        model_run_id=run_id,
        created_at=datetime.now(tz=UTC),
        one_liner="Trotz normalem Model markiert als Error",  # KEIN String-Match
        ranking_interpretation="x" * 100,
        sweet_spot=False,
        sweet_spot_explanation=None,
        contradictions=[],
        key_strengths=["—"],
        key_risks=["—"],
        confidence="low",
        model_version="claude-sonnet-4-6",  # KEIN Sentinel
        is_error=True,  # nur das ist gesetzt
    )
    await repo.save(memo)

    response = await client.get(f"/api/v1/memos/{stock_id}/{run_id}")

    assert response.status_code == 200
    assert response.json()["is_error"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/integration/test_memos_endpoint.py::test_memo_response_is_error_uses_entity_field_not_string_match -v
```

Expected: FAIL — Router-Logik leitet `is_error` aktuell aus `model_version=='error-fallback'` OR string-match ab; both falsch hier → `is_error: False` returned.

- [ ] **Step 3: Modify `MemoResponse.from_entity` (memos.py:61-82)**

Replace the heuristic block:

```python
    @classmethod
    def from_entity(cls, memo: ResearchMemo) -> "MemoResponse":
        return cls(
            id=memo.id,
            stock_id=memo.stock_id,
            model_run_id=memo.model_run_id,
            language=memo.language,
            one_liner=memo.one_liner,
            ranking_interpretation=memo.ranking_interpretation,
            sweet_spot=memo.sweet_spot,
            sweet_spot_explanation=memo.sweet_spot_explanation,
            contradictions=list(memo.contradictions),
            key_strengths=list(memo.key_strengths),
            key_risks=list(memo.key_risks),
            confidence=memo.confidence,
            model_version=memo.model_version,
            created_at=memo.created_at,
            is_error=memo.is_error,
        )
```

(Removes the `is_error = memo.model_version == ERROR_FALLBACK_MODEL_VERSION or memo.one_liner.startswith(...)` block and the `is_error` local variable.)

- [ ] **Step 4: Modify `BatchMemoSummary`-Build (memos.py:185)**

In the `get_job` endpoint, replace line ~185:

```python
    memo_summaries = [
        BatchMemoSummary(
            stock_id=m.stock_id,
            ticker=ticker_map.get(m.stock_id),
            one_liner=m.one_liner,
            is_error=m.is_error,
        )
        for m in memos
    ]
```

(`ERROR_FALLBACK_MODEL_VERSION` import in this file is then possibly unused — check and remove if so.)

- [ ] **Step 5: Run integration tests to verify they pass**

```bash
uv run pytest backend/tests/integration/test_memos_endpoint.py backend/tests/integration/test_memo_batch_full_flow.py -v
```

Expected: alle PASS einschließlich neuer Test + bestehende `assert body["is_error"] is True/False`-Tests.

- [ ] **Step 6: Commit**

```bash
git add backend/interfaces/rest/routers/memos.py \
        backend/tests/integration/test_memos_endpoint.py
git commit -m "refactor(rest): is_error direkt aus Entity statt String-Match (#67)

MemoResponse.from_entity und BatchMemoSummary-Build nutzen memo.is_error
direkt. Heuristik 'startswith(\"Memo-Generierung fehlgeschlagen\")' und
'== ERROR_FALLBACK_MODEL_VERSION' fliegt aus dem Router — EN-Memos waren
sonst nach #116-Merge false-negative.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Helper-Score-Removal `_rankings_for_template`

**Files:**
- Modify: `backend/application/services/narrative_service.py:104-125`
- Test: `backend/tests/unit/application/test_narrative_service.py`

- [ ] **Step 1: Write failing unit test**

Append to `backend/tests/unit/application/test_narrative_service.py`:

```python
def test_rankings_for_template_returns_only_rank_no_score() -> None:
    """Issue #66: erfundener Score (1/rank) entfernt — nur reale Rank-Daten."""
    from backend.application.services.narrative_service import _rankings_for_template

    out = _rankings_for_template({
        "per_model_ranks": {
            "quality_classic": 8,
            "alpha": 12,
            "trend_momentum": 25,
            "value_alpha_potential": 60,
            "diversification": 5,
        }
    })

    assert out == {
        "Quality Classic": {"rank": 8},
        "Alpha": {"rank": 12},
        "Trend Momentum": {"rank": 25},
        "Value Alpha Potential": {"rank": 60},
        "Diversification": {"rank": 5},
    }
    # Explizit: kein score-Key in irgendeinem Modell
    for model_data in out.values():
        assert "score" not in model_data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py::test_rankings_for_template_returns_only_rank_no_score -v
```

Expected: FAIL — output contains `score` keys.

- [ ] **Step 3: Modify `_rankings_for_template` (line 104-125)**

Replace the function body:

```python
def _rankings_for_template(ranking: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Wandelt das per_model_ranks-Dict in ein Template-freundliches
    dict[name, {rank}]-Format um.

    Score-Werte werden bewusst NICHT mitgeführt: vor Issue #66 wurde
    score = 1 / rank als Proxy berechnet, was die LLM als echte
    quantitative Aussage interpretiert hat (Hallucination-Quelle).
    Sobald echte per-Modell-Scores in Run-Results landen, kann der
    Slot reaktiviert werden.
    """
    model_label = {
        "quality_classic": "Quality Classic",
        "alpha": "Alpha",
        "trend_momentum": "Trend Momentum",
        "value_alpha_potential": "Value Alpha Potential",
        "diversification": "Diversification",
    }
    out: dict[str, dict[str, int]] = {}
    per_model = ranking.get("per_model_ranks") or {}
    for key, label in model_label.items():
        rank = per_model.get(key)
        if rank is not None:
            out[label] = {"rank": int(rank)}
    return out
```

(Type-Signature: `dict[str, dict[str, float | int]]` → `dict[str, dict[str, int]]` — auch das anpassen.)

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py::test_rankings_for_template_returns_only_rank_no_score -v
```

Expected: PASS.

- [ ] **Step 5: Run mypy to verify type narrowing OK**

```bash
uv run mypy --strict backend
```

Expected: 0 errors. Wenn callsite vom Helper engere Typen erwartet hat (war zuvor `float | int`), kann es minimale Adjustments brauchen.

- [ ] **Step 6: Commit**

```bash
git add backend/application/services/narrative_service.py \
        backend/tests/unit/application/test_narrative_service.py
git commit -m "fix(narrative): _rankings_for_template ohne erfundenen Score (#66)

Score=1/rank war Hallucination-Quelle: erfundene Float-Werte wurden ins
User-Prompt gerendert und vom System-Prompt-Few-Shot durch echt-aussehende
Beispiele flankiert. LLM hat das als quantitative Aussage interpretiert.
Helper liefert jetzt nur reale Rank-Daten.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: DE-User-Template Score-Removal + Snapshot-Update

**Files:**
- Modify: `backend/infrastructure/llm/prompts/narrative_user.de.md.j2`
- Modify: `backend/tests/fixtures/prompts/expected_user_prompt.de.md`
- Modify: `backend/tests/unit/infrastructure/test_prompt_loader.py`

**Note:** Datei-Existenz nach #116-Merge: `narrative_user.de.md.j2` (umbenannt von `narrative_user.md.j2`). Falls noch das alte File ohne `.de.` vorliegt → #116 ist nicht gemerged → Pre-Execution-Check failed → STOP.

- [ ] **Step 1: Update test fixture (Snapshot)**

Edit `backend/tests/fixtures/prompts/expected_user_prompt.de.md` (oder `.md`). Lines 12-16 enthalten aktuell:
```
- Quality Classic: Rang 8/80, Score 0.8700
- Alpha: Rang 12/80, Score 0.7400
- Trend Momentum: Rang 25/80, Score 0.6200
- Value Alpha Potential: Rang 60/80, Score 0.3100
- Diversification: Rang 5/80, Score 0.9100
```

Ersetze mit:
```
- Quality Classic: Rang 8/80
- Alpha: Rang 12/80
- Trend Momentum: Rang 25/80
- Value Alpha Potential: Rang 60/80
- Diversification: Rang 5/80
```

- [ ] **Step 2: Update test input dict (test_prompt_loader.py)**

Edit `backend/tests/unit/infrastructure/test_prompt_loader.py`, `rankings` dict in `test_render_user_prompt_matches_snapshot` (~line 29):

Von:
```python
            "rankings": {
                "Quality Classic": {"rank": 8, "score": 0.87},
                "Alpha": {"rank": 12, "score": 0.74},
                "Trend Momentum": {"rank": 25, "score": 0.62},
                "Value Alpha Potential": {"rank": 60, "score": 0.31},
                "Diversification": {"rank": 5, "score": 0.91},
            },
```

zu:
```python
            "rankings": {
                "Quality Classic": {"rank": 8},
                "Alpha": {"rank": 12},
                "Trend Momentum": {"rank": 25},
                "Value Alpha Potential": {"rank": 60},
                "Diversification": {"rank": 5},
            },
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py::test_render_user_prompt_matches_snapshot -v
```

Expected: FAIL — Template rendert noch `Score {{ "%.4f"|format(ranking.score) }}` → `UndefinedError: 'dict object' has no attribute 'score'` OR ein Snapshot-Mismatch.

- [ ] **Step 4: Modify DE-User-Template**

Edit `backend/infrastructure/llm/prompts/narrative_user.de.md.j2` line 14:

Von:
```jinja
{% for model_name, ranking in rankings.items() %}- {{ model_name }}: Rang {{ ranking.rank }}/{{ n_stocks }}, Score {{ "%.4f"|format(ranking.score) }}
```

zu:
```jinja
{% for model_name, ranking in rankings.items() %}- {{ model_name }}: Rang {{ ranking.rank }}/{{ n_stocks }}
```

- [ ] **Step 5: Run snapshot test to verify it passes**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py -v
```

Expected: alle PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/infrastructure/llm/prompts/narrative_user.de.md.j2 \
        backend/tests/fixtures/prompts/expected_user_prompt.de.md \
        backend/tests/unit/infrastructure/test_prompt_loader.py
git commit -m "fix(narrative): DE-User-Template ohne Score-Spalte (#66)

User-Prompt rendert nur \"Rang X/N\" — die erfundene Score-Spalte (1/rank)
flog im Helper raus, das Template muss konsequent nachziehen. Fixture +
Test-Input-Dict aktualisiert.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: DE-System-Prompt Few-Shot Score-Removal

**Files:**
- Modify: `backend/infrastructure/llm/prompts/narrative_system.de.md.j2`
- Test: `backend/tests/unit/infrastructure/test_prompt_loader.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/unit/infrastructure/test_prompt_loader.py`:

```python
def test_de_system_prompt_few_shot_has_no_score_values() -> None:
    """Issue #66: Few-Shot-Beispiel im System-Prompt darf keine erfundenen
    Score-Werte enthalten — sonst trainiert die LLM auf Score-Wording."""
    loader = PromptTemplateLoader()
    rendered = loader.render("narrative_system.de.md.j2", {})
    # Konkrete Score-Werte aus dem alten Few-Shot dürfen nicht mehr vorkommen
    for forbidden in ["Score 0.87", "Score 0.74", "Score 0.62", "Score 0.31", "Score 0.91"]:
        assert forbidden not in rendered, f"System-Prompt enthält noch {forbidden!r}"
    # Generelle Sanity: Few-Shot-Block ist noch da
    assert "Quality Classic" in rendered
    assert "Rang" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py::test_de_system_prompt_few_shot_has_no_score_values -v
```

Expected: FAIL — `Score 0.87` ist noch im System-Prompt.

- [ ] **Step 3: Edit narrative_system.de.md.j2 Few-Shot (~line 118-122)**

Find the lines:
```
- Quality Classic: Rang 8/80, Score 0.87
- Alpha: Rang 12/80, Score 0.74
- Trend Momentum: Rang 25/80, Score 0.62
- Value Alpha Potential: Rang 60/80, Score 0.31
- Diversification: Rang 5/80, Score 0.91
```

Replace with:
```
- Quality Classic: Rang 8/80
- Alpha: Rang 12/80
- Trend Momentum: Rang 25/80
- Value Alpha Potential: Rang 60/80
- Diversification: Rang 5/80
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py -v
```

Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/infrastructure/llm/prompts/narrative_system.de.md.j2 \
        backend/tests/unit/infrastructure/test_prompt_loader.py
git commit -m "fix(narrative): DE-System-Prompt Few-Shot ohne Score (#66)

Few-Shot-Block hatte echt-aussehende Score-Werte (0.87, 0.74, ...), die
das LLM-Output-Wording subtil auf Score-Sprache trainierten. Konsistent
mit Helper + User-Template-Cleanup: nur Rang, keine Erfindung.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: EN-Symmetrie — User-Template + System-Prompt

**Files:**
- Modify: `backend/infrastructure/llm/prompts/narrative_user.en.md.j2`
- Modify: `backend/infrastructure/llm/prompts/narrative_system.en.md.j2`
- Modify: `backend/tests/fixtures/prompts/expected_user_prompt.en.md`

**Pre-Check:**
```bash
ls backend/infrastructure/llm/prompts/narrative_user.en.md.j2 backend/infrastructure/llm/prompts/narrative_system.en.md.j2
```
Beide müssen existieren (kommen mit PR #116). Wenn nicht: STOP, EN-Symmetrie wartet auf #116-Merge.

- [ ] **Step 1: Edit EN-User-Template — analog Task 7**

Im File `narrative_user.en.md.j2` die Zeile mit Score-Format suchen:
```jinja
{% for model_name, ranking in rankings.items() %}- {{ model_name }}: Rank {{ ranking.rank }}/{{ n_stocks }}, Score {{ "%.4f"|format(ranking.score) }}
```

(Exakte Wording kann `Rank` oder `Rang` sein — siehe #116-Mergetransform.)

Ersetzen mit (Score-Spalte raus):
```jinja
{% for model_name, ranking in rankings.items() %}- {{ model_name }}: Rank {{ ranking.rank }}/{{ n_stocks }}
```

- [ ] **Step 2: Edit EN-Fixture `expected_user_prompt.en.md`**

Score-Werte analog Task 7 raus aus den 5 Modell-Zeilen.

- [ ] **Step 3: Edit EN-System-Prompt Few-Shot — analog Task 8**

In `narrative_system.en.md.j2`, Few-Shot-Block (analog zu DE-Variante Z. 118-122) Score-Werte entfernen.

- [ ] **Step 4: Add EN-System-Prompt no-score test**

Append to `test_prompt_loader.py`:

```python
def test_en_system_prompt_few_shot_has_no_score_values() -> None:
    """Issue #66 EN-Symmetrie: kein erfundener Score im EN-System-Prompt."""
    loader = PromptTemplateLoader()
    rendered = loader.render("narrative_system.en.md.j2", {})
    for forbidden in ["Score 0.87", "Score 0.74", "Score 0.62", "Score 0.31", "Score 0.91"]:
        assert forbidden not in rendered, f"EN-System-Prompt enthält noch {forbidden!r}"
    assert "Quality Classic" in rendered
```

- [ ] **Step 5: Add/Update EN-User-Snapshot-Test**

In `test_prompt_loader.py`, EN-Variante:

```python
def test_render_en_user_prompt_matches_snapshot() -> None:
    """EN-Symmetrie für User-Prompt — Score-Spalte ist auch hier raus (#66)."""
    loader = PromptTemplateLoader()
    rendered = loader.render(
        "narrative_user.en.md.j2",
        {
            "ticker": "NESN",
            "name": "Nestle SA",
            "sector": "Consumer Staples",
            "country": "CH",
            "run_id": "550e8400-e29b-41d4-a716-446655440001",
            "universe_name": "Swiss-Mid-Cap",
            "n_stocks": 80,
            "median_rank": 40,
            "top20_threshold": 16,
            "rankings": {
                "Quality Classic": {"rank": 8},
                "Alpha": {"rank": 12},
                "Trend Momentum": {"rank": 25},
                "Value Alpha Potential": {"rank": 60},
                "Diversification": {"rank": 5},
            },
            "total_rank": 11,
            "sweet_spot": True,
            "weights": "equal-weighted (0.20 each)",
        },
    )
    expected = (FIXTURES / "expected_user_prompt.en.md").read_text(encoding="utf-8").rstrip()
    assert rendered.rstrip() == expected
```

(Falls bereits ein EN-User-Snapshot-Test in #116 angelegt wurde: nur das `rankings`-Dict anpassen statt Test neu schreiben.)

- [ ] **Step 6: Run all prompt-loader tests**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py -v
```

Expected: alle PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/infrastructure/llm/prompts/narrative_user.en.md.j2 \
        backend/infrastructure/llm/prompts/narrative_system.en.md.j2 \
        backend/tests/fixtures/prompts/expected_user_prompt.en.md \
        backend/tests/unit/infrastructure/test_prompt_loader.py
git commit -m "fix(narrative): EN-Template-Symmetrie für Score-Removal (#66)

User-Template + System-Prompt-Few-Shot analog DE entkernt. Cache-Hash
für EN-System-Block bricht einmalig (~2100 Tokens neu cachen) — Cents.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: AI-USAGE.md Eintrag

**Files:**
- Modify: `docs/AI-USAGE.md`

- [ ] **Step 1: Add new entry at top of "Einträge" section**

Edit `docs/AI-USAGE.md`. Direkt nach `## Einträge` (vor dem ersten existierenden Eintrag) einfügen:

```markdown
## 2026-05-14 · Narrative-Followups Bundle #66 + #67 (PR #__)
- **Agent**: Claude Code (Opus 4.7) im Haupt-Context. Skills: `superpowers:brainstorming` (4 Q-by-Q-Fragen), `superpowers:writing-plans` (10-Task-Plan), `superpowers:test-driven-development` (RED→GREEN pro Task), `superpowers:verification-before-completion` (CI-Mirror lokal + Real-API-Smoke).
- **Scope**: Zwei thematisch zusammengehörige Folge-Fixes aus PR #64-Review als 1 PR. (a) **#66** — `_rankings_for_template`-Helper liefert keinen erfundenen `score = 1/rank` mehr; DE + EN User-Templates und System-Prompt-Few-Shots ohne Score-Werte. (b) **#67** — `is_error: bool` als reguläres Feld auf `ResearchMemo`-Entity + ORM-Spalte + Migration 0009 + Backfill via Sentinel; Router-String-Match (`one_liner.startswith("Memo-Generierung fehlgeschlagen")`) entkernt — kritisch für EN-Memos, die der String-Match nach #116-Merge false-negative gemeldet hätte. `ERROR_FALLBACK_MODEL_VERSION`-Sentinel bleibt als zusätzliche DB-Markierung.
- **Real-API-Smoke (DE, Sonnet 4.6)**: [WERTE NACH SMOKE-RUN EINTRAGEN]
- **Was gut lief**:
  - [Nach Implementation eintragen]
- **Was nicht klappte**:
  - [Nach Implementation eintragen]
- **Lektion**: [Nach Implementation eintragen]
- **Token-Kosten**: [Nach Session eintragen]
- **Autor**: Sheyla Sampietro (mit Claude Code)
```

- [ ] **Step 2: Commit (placeholder, wird in Task 11 nachgefüllt)**

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): Narrative-Followups Bundle #66+#67 — Slice-Eintrag

Strukturierter Eintrag mit Scope + Skills. Real-API-Smoke-Werte +
Reflexionen folgen nach Implementation und Smoke-Run (Task 11).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Real-API-Smoke + AI-USAGE Reflexion

**Files:**
- Manual: `scripts/smoke_narrative_real_api.py` Run
- Modify: `docs/AI-USAGE.md` (Werte + Reflexion füllen)

- [ ] **Step 1: Set env + run smoke DE**

```bash
export ANTHROPIC_API_KEY=<dein-key>
python -m backend.scripts.smoke_narrative_real_api --lang=de 2>&1 | tee /tmp/smoke_de.log
```

Expected: 2 Calls, beide grün gegen `ResearchMemoSchema`. Cache-Read auf Call 2.

- [ ] **Step 2: Verify Output enthält keinen erfundenen Score**

```bash
grep -i "score" /tmp/smoke_de.log
```

Expected: keine `Score 0.XX`-Erwähnung im Memo-Output. Wenn doch: Anti-Hallucination-Wirkung verifizieren, ggf. System-Prompt nachschärfen.

- [ ] **Step 3 (optional, wenn #116 + EN-Templates aktiv): Run smoke EN**

```bash
python -m backend.scripts.smoke_narrative_real_api --lang=en 2>&1 | tee /tmp/smoke_en.log
grep -i "score" /tmp/smoke_en.log
```

- [ ] **Step 4: Update AI-USAGE.md mit Smoke-Werten + Reflexionen**

In den in Task 10 angelegten Eintrag die Felder füllen:
- Real-API-Smoke-Tabelle (Input, Output, Cache-Create, Cache-Read, Latenz, Kosten — aus Smoke-Log)
- Was gut lief (Q-by-Q, TDD-Discipline, Bundle-Strategie)
- Was nicht klappte (jede Unerwartete während Implementation)
- Lektion (1 zentrale)
- Token-Kosten

- [ ] **Step 5: Run full CI-Mirror local**

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run mypy --strict backend
uv run pytest backend/tests/unit -v
```

Expected: alles grün.

- [ ] **Step 6: Commit**

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): Smoke-Werte + Reflexion für Narrative-Followups-Bundle

Real-API-Smoke DE [+ EN] dokumentiert, Wirkung des Score-Removals
verifiziert, methodische Lehren extrahiert.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: PR erstellen + Ready for Review

- [ ] **Step 1: Push branch + create PR (draft → ready)**

```bash
git push -u origin feat/narrative-followups-66-67
gh pr create --draft --title "fix(narrative): Score-Hallucination + is_error-Refactor Bundle (#66, #67)" --body "$(cat <<'EOF'
## Was & Warum

Zwei Folge-Fixes aus PR #64-Review als 1 Bundle (PR-Body referenziert die Spec).

### #66 — Score=1/rank Hallucination raus
- `_rankings_for_template` liefert nur reale Ranks, keinen erfundenen Score
- DE + EN User-Templates ohne `Score X.XXXX`-Spalte
- DE + EN System-Prompt-Few-Shots ohne `Score 0.87`-Beispiele
- Real-API-Smoke verifiziert: LLM erwähnt keinen erfundenen Score mehr

### #67 — is_error als Entity-Feld
- Migration 0009: ADD COLUMN is_error + Backfill via Sentinel
- ORM-Spalte + Repository-Roundtrip
- `_build_memo_entity` setzt is_error aus `model_version == ERROR_FALLBACK_MODEL_VERSION` (Single-Point-of-Truth)
- Router liest `memo.is_error` direkt — String-Match entfernt
- `ERROR_FALLBACK_MODEL_VERSION`-Sentinel bleibt als zusätzliche DB-Markierung

## Closes
- Closes #66
- Closes #67

## Spec & Plan
- `docs/specs/2026-05-14-narrative-followups-66-67.md`
- `docs/specs/2026-05-14-narrative-followups-66-67-plan.md`

## Test plan
- [ ] Unit-Tests: Entity, Helper, Bridge, Templates (alle Snapshots)
- [ ] Integration-Tests: Migration, Repository-Roundtrip, Router-is_error-direct
- [ ] Manual: Real-API-Smoke DE + EN (Werte in AI-USAGE.md)
- [ ] CI: ruff, mypy strict, pytest unit + integration, coverage ≥80%

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Wait for CI, mark Ready-for-Review**

```bash
gh pr checks <PR-NUMBER>
# When all green:
gh pr ready <PR-NUMBER>
```

---

## Notes for Executor

- **Order matters.** Tasks 1→8 sind eine TDD-Kette: Entity → Migration → ORM → Bridge → Router → Helper → Templates. Task 9 (EN) ist optional-additiv (siehe Pre-Check). Task 10+11 sind Doku/Verification.
- **Pre-Execution-Check ist hart.** Wenn PR #116 nicht gemerged ist: NICHT STARTEN. Spec §5 erklärt warum.
- **Bestehende Tests müssen grün bleiben.** Nach jedem Task: `uv run pytest backend/tests/unit -v` als Sanity-Check.
- **Commit-Disziplin.** Jeder Task = ein logischer Commit. Mehrere Commits pro Task nur wenn ein Schritt vergessen wurde (Fixup-Commit).
- **Pre-Push-CI-Mirror.** Bevor `git push`: `ruff check + ruff format --check + mypy --strict + pytest unit`. Siehe Memory `feedback_pre_push_ci_mirror`.
