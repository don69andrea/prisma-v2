# Spec: Narrative Engine — Foundation (PR #1 für Issue #17)

**Status**: Draft v1.0 — 2026-04-30
**Rolle**: B — AI Engineer (Sheyla)
**Parent-Spec**: [`2026-04-28-narrative-engine.md`](2026-04-28-narrative-engine.md)
**Issue**: [#17](https://github.com/SheylaSam/prisma-capstone/issues/17) — feat(ai): Narrative-Engine (Layer 1) — Scaffold + ResearchMemo-Schema

---

## Inhaltsverzeichnis

1. [Zweck & Abgrenzung](#1-zweck--abgrenzung)
2. [Scope](#2-scope)
3. [Architektur-Entscheidungen aus Brainstorming](#3-architektur-entscheidungen-aus-brainstorming)
4. [DB-Schema (Migration)](#4-db-schema-migration)
5. [Pydantic-Klassen](#5-pydantic-klassen)
6. [Repository (Port + Adapter)](#6-repository-port--adapter)
7. [Test-Strategie](#7-test-strategie)
8. [Build-Order (5 Build-Steps für TDD)](#8-build-order-5-build-steps-für-tdd)
9. [Akzeptanz-Kriterien](#9-akzeptanz-kriterien)
10. [Out-of-Scope für PR #1](#10-out-of-scope-für-pr-1)
11. [Änderungshistorie](#11-änderungshistorie)

---

## 1. Zweck & Abgrenzung

Diese Spec ist ein **Foundation-Subset** der Master-Spec [`2026-04-28-narrative-engine.md`](2026-04-28-narrative-engine.md). Sie deckt nur die Persistenz-Schicht der Narrative Engine ab — genug für Issue #17 als erste mergebare PR.

**Was die Foundation liefert:**

- Pydantic-Schema für LLM-Output-Validierung (`ResearchMemoSchema`)
- Domain-Entity für persistierte Memos (`ResearchMemo`)
- Geteiltes Value-Object (`ContradictionItem`)
- DB-Tabelle `research_memos` mit Migration
- Repository-Port + SQLAlchemy-Adapter
- Tests für jede Schicht

**Was die Foundation NICHT liefert:** `NarrativeService`, LLM-Calls, Prompt-Templates, REST-Endpoints, Fixture-Mode-Tests, `/admin/llm-usage`-Endpoint. Alles das kommt in Folge-Issues, die nach PR #1 erstellt werden.

Begründung der Abgrenzung: Sheylas eigener Build-Stil aus PR #25 (#19 Budget-Cap) — Implementation in 11 Build-Steps, jede mergebar, klare Review-Grenzen. Hier analog: Foundation in 5 Build-Steps in einer PR, dann Service/REST in Folge-PRs.

---

## 2. Scope

### In Scope (PR #1)

- `backend/domain/entities/research_memo.py` — `ResearchMemo` Entity + `ContradictionItem` Value-Object
- `backend/domain/schemas/research_memo_schema.py` — `ResearchMemoSchema` LLM-Vertrag
- `backend/domain/repositories/research_memo_repository.py` — `ResearchMemoRepository` ABC (Port)
- `backend/infrastructure/persistence/models/research_memo.py` — `ResearchMemoORM` SQLAlchemy-Modell
- `backend/infrastructure/persistence/repositories/research_memo_repository.py` — `SQLAResearchMemoRepository` Adapter
- `backend/alembic/versions/0005_create_research_memos.py` — Migration
- `backend/alembic/env.py` — Import-Ergänzung für Auto-Discovery
- Tests: 4 neue Test-Files (siehe §7)

### Out of Scope (Folge-Issues)

- `NarrativeService` (Application-Layer)
- `ClaudeLLMClient`-Erweiterung um Memo-Generation (existierender `LLMClient` aus PR #25 wird später erweitert)
- Prompt-Templates (`narrative_system.{de,en}.md.j2`, `narrative_user.md.j2`)
- 4 REST-Endpoints aus Master-Spec §8
- Fixture-Mode-Tests, Golden-Prompt-Workflow
- `llm_usage_log`-Tabelle (existiert bereits als `llm_call_log` aus PR #25 — Master-Spec §11.2 sollte synchronisiert werden, aber separater Doc-Fix)

---

## 3. Architektur-Entscheidungen aus Brainstorming

Brainstorming-Session 2026-04-30 mit Claude Code (Opus 4.7). Vier strukturelle Entscheidungen, die die Foundation prägen:

### 3.1 UNIQUE-Constraint auf `(stock_id, model_run_id, language)`

**Entschieden:** UNIQUE-Constraint, Re-Generate via UPSERT.

**Alternative diskutiert:** Multiple Memos pro `(stock, run)` mit Versionierung.

**Begründung:**
- Spec §13 Q5 deutet auf "neue Rankings = neue Story" — innerhalb desselben Runs gibt's wenig Grund für mehrere Memos pro Stock.
- `llm_call_log` (existiert seit PR #25) deckt Audit-Aspekt ab — Versionierung im Memo wäre Redundanz.
- UI-mäßig: ein Stock zeigt **ein** Memo pro Run und Sprache. Natural expectation.
- Falls Versionierung später wirklich gebraucht: `DROP CONSTRAINT` + `ADD version` ist eine Migration weg, kein Lock-in.

### 3.2 Sprach-Spalte ab Tag 1

**Entschieden:** `language VARCHAR(2) NOT NULL DEFAULT 'de'` ab dieser Migration.

**Alternative diskutiert:** Implizit "de", spätere Migration für Bilingual.

**Begründung:**
- Master-Spec §2 hat eine explizite "Sprach-Architektur-Notiz" — bilingual vorbereitet, aber MVP nur DE.
- Master-Spec §13 Q3 markiert Bilingual-Support als **entschieden** (Sheyla, 2026-04-21).
- Kosten heute: 1 Spalte + Constraint mit 3 statt 2 Feldern. Migration heute statt später.
- Die DB sollte das Versprechen der Spec spiegeln. Konsequenz statt Drift.

### 3.3 Schema-vs-Entity-Trennung (zwei Klassen)

**Entschieden:** `ResearchMemoSchema` (LLM-Vertrag) und `ResearchMemo` (Entity) als **getrennte Klassen**, ohne Vererbung.

**Alternativen diskutiert:**
- Eine Klasse mit Optional-Feldern (vermischt Concerns)
- Vererbung `ResearchMemo(ResearchMemoSchema)` (Schema-Constraint-Drift wirkt auf alte DB-Daten)

**Begründung:**
- LLM-Schema ist API-Vertrag, der mit Prompt-Iterationen co-evolviert. Entity ist persistierter Output mit eigenem Lebenszyklus.
- `ticker`/`total_rank` sind im LLM-Schema (Sanity-Check), in Entity via FK referenziert — keine doppelte Speicherung.
- Wenn Schema-Constraints später schärfer werden (z.B. `min_length=20` für `one_liner`), brechen alte DB-Einträge bei Vererbung. Mit Trennung: Entity bleibt stabil, nur Schema ändert sich.

### 3.4 Entity ist `frozen=True`

**Entschieden:** `ResearchMemo` und `ContradictionItem` sind beide Pydantic-`frozen`.

**Begründung:**
- Domain-Entities sollten Immutable sein. Mutation passiert via "neues Entity erzeugen", nicht via Feld-Mutation.
- Defensive-Coding: verhindert versehentliche In-Place-Modifikation in Service-Code.
- Re-Generate ist ohnehin UPSERT (neuer Datenbank-Zustand), nicht in-place-Update.

---

## 4. DB-Schema (Migration)

```sql
CREATE TABLE research_memos (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id                 UUID NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    model_run_id             UUID NOT NULL REFERENCES ranking_runs(id) ON DELETE CASCADE,
    language                 VARCHAR(2) NOT NULL DEFAULT 'de',
    created_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    one_liner                VARCHAR(150) NOT NULL,
    ranking_interpretation   VARCHAR(600) NOT NULL,
    sweet_spot               BOOLEAN NOT NULL,
    sweet_spot_explanation   VARCHAR(300),
    contradictions           JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_strengths            JSONB NOT NULL,
    key_risks                JSONB NOT NULL,
    confidence               VARCHAR(10) NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    model_version            VARCHAR(64) NOT NULL,

    CONSTRAINT uq_research_memos_stock_run_lang
        UNIQUE (stock_id, model_run_id, language)
);

CREATE INDEX ix_research_memos_model_run_id ON research_memos(model_run_id);
```

### Felder, die NICHT in der DB sind (relativ zur Master-Spec §4)

| Feld | Wo statt | Begründung |
|------|----------|------------|
| `ticker` | derivierbar via `stock_id → stocks.ticker` | LLM-Echo zur Sanity-Check, keine Persistenz nötig |
| `total_rank` | derivierbar via `model_run_id → ranking_runs.results` | gleicher Grund |
| `generated_at` | kollabiert zu `created_at` | LLM-Output-Timestamp ist nicht vertrauenswürdig (LLM könnte halluzinieren); DB-Side `now()` reicht |

### CASCADE-Verhalten

- `stocks.id` gelöscht → alle Memos für diesen Stock weg
- `ranking_runs.id` gelöscht → alle Memos für diesen Run weg
- Audit-Trail bleibt im `llm_call_log` (separater Lebenszyklus)

### Migration-Verifikation (manuell, im PR-Body dokumentieren)

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic upgrade head
```

Schema-Final-State muss diesem Spec entsprechen.

---

## 5. Pydantic-Klassen

### 5.1 `backend/domain/entities/research_memo.py`

```python
from datetime import datetime
from typing import Literal
from uuid import UUID
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

### 5.2 `backend/domain/schemas/research_memo_schema.py`

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from backend.domain.entities.research_memo import ContradictionItem


class ResearchMemoSchema(BaseModel):
    """LLM-Output-Vertrag — was wir von Claude erwarten.

    Master-Spec §4 wortgetreu, mit allen Validation-Constraints
    (min_length, max_length, max_length auf Listen). Wird im Service
    zu ResearchMemo (Entity) gemappt — Mapping kommt in Folge-PR.
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

### Constraint-Asymmetrie (bewusste Design-Entscheidung)

| Feld | Schema | Entity |
|------|--------|--------|
| `one_liner` | `min_length=10, max_length=150` | nur `max_length=150` |
| `ranking_interpretation` | `min_length=100, max_length=600` | nur `max_length=600` |
| `key_strengths` | `min_length=1, max_length=5` | keine Length-Validation |
| `contradictions` | `max_length=3` | keine Length-Validation |

**Konsequenz:** Wenn das LLM-Schema später schärfer wird, bleiben alte DB-Einträge ladbar. Direktes Resultat von Entscheidung 3.3.

---

## 6. Repository (Port + Adapter)

### 6.1 Port: `backend/domain/repositories/research_memo_repository.py`

```python
from abc import ABC, abstractmethod
from typing import Literal
from uuid import UUID

from backend.domain.entities.research_memo import ResearchMemo


class ResearchMemoRepository(ABC):
    """Port für ResearchMemo-Persistenz."""

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

**Methoden, die NICHT in PR #1 sind:** `list_by_run`, `delete`, `exists`. Kommen mit dem Service.

### 6.2 Adapter: `backend/infrastructure/persistence/repositories/research_memo_repository.py`

Pattern-Vorlage: `SQLACostLogRepository` aus PR #25 — eigene `session_factory` pro Operation, vermeidet Transaction-Leaks.

**Wichtige Adapter-Details:**

- **`save` ist Postgres-spezifisch:** `pg_insert(...).on_conflict_do_update(...)`. Tests gegen echte Postgres im Container, kein SQLite-Mock-Pfad.
- **`created_at` ist nicht im UPDATE-Set** des UPSERT. Begründung: created_at ist Lifecycle-Marker des Original-Memos.
- **JSONB-Serialisierung** passiert im Adapter:
  - Save: `[c.model_dump() for c in memo.contradictions]`
  - Load: `[ContradictionItem(**d) for d in row.contradictions]`
- Entity bleibt Pydantic-rein, Adapter macht die Persistenz-Übersetzung.

---

## 7. Test-Strategie

| Datei | Tests | Was geprüft wird |
|-------|-------|------------------|
| `tests/unit/domain/schemas/test_research_memo_schema.py` | ~10 | Valid input ok; min/max-Verstöße auf alle String-/Listen-Felder; ungültiges `confidence`-Literal; `contradictions max_length=3`; `key_strengths`/`key_risks` min=1/max=5; `ContradictionItem` ist frozen |
| `tests/unit/domain/entities/test_research_memo.py` | ~6 | Valid construct mit allen Feldern; `language` default = `"de"`; Entity ist frozen (FrozenInstanceError); Constraint-Asymmetrie zum Schema (kurzer one_liner in Entity ok, im Schema nicht) |
| `tests/unit/infrastructure/test_research_memo_orm.py` | ~10 | Tablename `"research_memos"`; alle 14 Spalten + Typen; PK auf `id`; FK auf `stock_id`/`model_run_id` mit CASCADE; timezone-aware `created_at`; UNIQUE-Constraint-Name + Felder; CHECK-Constraint auf `confidence`; Index auf `model_run_id` |
| `tests/integration/persistence/test_research_memo_repository.py` | ~5 | Roundtrip Save→Get; Get nicht-existent → `None`; UPSERT überschreibt Schema-Felder, behält `created_at`; Multi-Language-Koexistenz (Save de + en für gleiche stock/run → beide bleiben); FK-Cascade (Stock löschen → Memos weg) |

**Coverage-Ziel:**
- Domain (Schema + Entity): ≥95%
- Infrastructure (ORM + Repository): ≥85%
- PR #1 gesamt: ≥90%

**Pytest-Fixture-Setup:** Bestehendes `tests/conftest.py` wird genutzt. Falls eine integration-spezifische Fixture fehlt, wird sie in `tests/integration/persistence/conftest.py` ergänzt — minimaler `truncate research_memos cascade`-Cleanup pro Test, kein vollständiges testcontainers-Setup (das ist Andreas Issue #39).

---

## 8. Build-Order (5 Build-Steps für TDD)

Build-Order folgt dem Sheyla-Pattern aus PR #25: jeder Step ist ein Commit, RED → GREEN, alle Quality-Gates grün vor dem nächsten.

| # | Build-Step | Files (neu) | Tests | Größe |
|---|------------|-------------|-------|-------|
| 1 | `ResearchMemoSchema` (Pydantic) + ContradictionItem | `domain/schemas/research_memo_schema.py`, `domain/entities/research_memo.py` (nur ContradictionItem zuerst) | `test_research_memo_schema.py` | ~30 Min |
| 2 | `ResearchMemo` Entity (Pydantic) | `domain/entities/research_memo.py` (Entity dazu) | `test_research_memo.py` | ~20 Min |
| 3 | ORM-Modell + Alembic-Migration | `infrastructure/persistence/models/research_memo.py`, `alembic/versions/0005_*.py`, `alembic/env.py` | `test_research_memo_orm.py` | ~30 Min |
| 4 | Repository-Port (ABC) | `domain/repositories/research_memo_repository.py` | (keine direkten Tests, ABC) | ~10 Min |
| 5 | SQLAResearchMemoRepository (Adapter) | `infrastructure/persistence/repositories/research_memo_repository.py` | `test_research_memo_repository.py` (Integration) | ~40 Min |

**Geschätzte Gesamtzeit:** ~2 h bei sauberem TDD-Flow. Kein Sog-Risiko in Service-Material — wenn Build-Step 5 grün ist, ist PR #1 fertig.

---

## 9. Akzeptanz-Kriterien

PR #1 ist mergebar, wenn:

- [ ] Build-Steps 1–5 alle grün, jeder als eigener Commit
- [ ] mypy strict ohne Fehler
- [ ] ruff check + ruff format clean
- [ ] pytest grün (existierende 148 Tests + ~31 neue)
- [ ] Coverage ≥90% auf neuen Files (Domain ≥95%, Infrastructure ≥85%)
- [ ] Alembic-Migration upgrade+downgrade-Roundtrip auf Live-DB verifiziert (im PR-Body dokumentiert)
- [ ] `backend/alembic/env.py` enthält Import-Statement für ResearchMemoORM (sonst Auto-Discovery fehlt)
- [ ] `docs/AI-USAGE.md`-Eintrag im selben PR (CONTRIBUTING.md-Konvention)
- [ ] PR-Beschreibung referenziert diese Spec + Issue #17
- [ ] Mindestens 1 Approval von Teammitglied (CONTRIBUTING.md)

---

## 10. Out-of-Scope für PR #1

Folgende Folge-Issues werde ich nach dem Spec-Approval anlegen:

| Folge-Issue (Vorschlag) | Scope | Größe |
|------------------------|-------|-------|
| feat(ai): NarrativeService — Schema→Entity-Mapping + Mock-LLM-Pfad | Service-Klasse, Mock-LLM-Tests, ohne echte Anthropic-Calls | mittel |
| feat(ai): ClaudeLLMClient erweitern um Memo-Generation | Methoden + Prompt-Caching auf existing `LLMClient` aus PR #25 | mittel |
| feat(ai): Prompt-Templates DE (Jinja2) | `narrative_system.de.md.j2`, `narrative_user.md.j2`, Snapshot-Tests | mittel |
| feat(rest): 4 Memo-Endpoints aus Master-Spec §8 | POST generate, POST batch, GET, POST regenerate | mittel |
| feat(test): Fixture-Mode + Golden-Prompt-Workflow | 5 Golden-Fixtures, llm-smoke.yml CI-Workflow | groß |
| docs(spec): Master-Narrative-Engine-Spec synchronisieren mit Code | `llm_usage_log` → `llm_call_log`, `ClaudeLLMClient` → existierender `LLMClient` | klein |

Diese werden nach Spec-Approval als GitHub-Issues angelegt — nicht jetzt, weil sie nicht in PR #1 gehören.

---

## 11. Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| Draft v1.0 | 2026-04-30 | Sheyla / Claude Code | Initiale Foundation-Spec aus Brainstorming-Session. Vier Architektur-Entscheidungen (UNIQUE, language, schema-vs-entity, frozen) explizit dokumentiert. Build-Order in 5 TDD-Steps. |
