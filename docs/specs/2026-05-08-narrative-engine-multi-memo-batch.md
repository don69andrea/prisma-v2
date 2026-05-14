# Spec: Narrative Engine — Multi-Memo Batch (AI Layer 1, Folge-Slice)

**Status**: Draft v1.0 — 2026-05-08
**Rolle**: B — AI Engineer (Sheyla)
**Parent-Spec**: `docs/specs/2026-04-28-narrative-engine.md` §8 (`batch_generate_memos` + `POST /api/v1/memos/batch`)
**Vorgänger-Slice**: `docs/specs/2026-05-04-narrative-engine-single-memo.md` (Single-Memo-Pfad, PR #64)

---

## Inhaltsverzeichnis

1. [Zweck & Nutzerwert](#1-zweck--nutzerwert)
2. [Scope](#2-scope)
3. [Architektur-Überblick](#3-architektur-überblick)
4. [Domain & Persistence](#4-domain--persistence)
5. [Service-API](#5-service-api)
6. [REST-API + Data-Flow](#6-rest-api--data-flow)
7. [Cost & Caching](#7-cost--caching)
8. [Error-Handling](#8-error-handling)
9. [Test-Strategie](#9-test-strategie)
10. [Akzeptanz-Kriterien](#10-akzeptanz-kriterien)
11. [Bewusste Abweichungen von Parent-Spec](#11-bewusste-abweichungen-von-parent-spec)
12. [Offene Entscheidungen](#12-offene-entscheidungen)
13. [Änderungshistorie](#13-änderungshistorie)

---

## 1. Zweck & Nutzerwert

> **TL;DR (Reviewer):** Statt 20 Memos einzeln per Klick zu generieren, ein Klick → 20 Memos für Top-N Stocks eines Runs. Live-Progress, robust gegen einzelne Fails.

Die Single-Memo-Slice (PR #64) hat den Pfad gebaut: für *eine* Aktie generieren wir ein strukturiertes Memo. Für eine Demo oder produktive Nutzung reicht das nicht — ein Portfolio-Manager will die Top-20 eines Runs zusammen sehen, nicht 20 mal "Generate"-Klicks.

Diese Slice fügt den Multi-Memo-Pfad hinzu:

- **Ein User-Klick** auf "Memos für Top-N generieren"
- **Async-Job** im Backend, sofortige 202-Response mit Job-ID
- **Live-Progress** im Frontend: "12 von 20 fertig", neue Memos erscheinen wie sie generiert werden
- **Best-Effort**: einzelne Fails kippen den ganzen Batch nicht
- **Cache-effizient**: Anthropic-Prompt-Caching gibt uns ~95% Cache-Hits ab Memo 2 → Kosten halbiert

---

## 2. Scope

> **TL;DR (Reviewer):** In: Batch-Endpoint mit Job-Pattern + Live-Progress + Error-Resilience + Cost-Cap. Out: Cancel-Funktionalität, Auto-Cleanup, Webhook-Notifikation.

### In Scope

- **Service-Methode** `NarrativeService.start_batch(model_run_id, top_n=20, language="de")` — erstellt Job, startet Background-Worker, returnt sofort
- **Background-Worker** `_execute_batch(job_id)` — generiert Memos für Top-N Stocks parallel mit Semaphore-Limit 3 (konfigurierbar)
- **Job-Persistenz** in neuer Tabelle `memo_batch_jobs` mit Status-Lifecycle (pending → running → complete/partial/failed)
- **REST-Endpoints**:
  - `POST /api/v1/memos/batch` → 202 + Job-ID
  - `GET /api/v1/memos/jobs/{job_id}` → Status + Progress + bisherige Memos
- **Cost-Pre-Check**: vor Job-Start `CostTracker.check_cap` mit `estimated_usd = top_n × ~$0.025`
- **Stale-Job-Cleanup**: lazy beim GET — Jobs mit `started_at + STALE_TIMEOUT < now()` werden zu `failed` gemarkt
- **Wiederverwendung**: ruft das bestehende `NarrativeService.generate_memo` (Single-Memo-Slice) per Stock auf — kein Duplicate-Code

### Out of Scope

- **Cancel-Funktionalität**: User kann laufenden Job nicht stoppen (Folge-PR wenn relevant)
- **Auto-Cleanup alter Jobs**: Job-Tabelle wächst unbegrenzt (Folge-PR wenn DB-Volumen problematisch wird)
- **Webhook-Benachrichtigung**: kein Push an Frontend, nur Polling
- **Multi-Language im selben Batch**: ein Batch ist immer eine Sprache (de oder en)
- **Scheduling**: keine wiederkehrenden/zeitversetzten Batches
- **Anthropic Message Batches API**: 50% Discount, aber 24h-SLA passt nicht zum Demo-Use-Case (siehe §11)

---

## 3. Architektur-Überblick

> **TL;DR (Reviewer):** Hexagonal-Architektur konsistent mit Single-Memo. Neue Tabelle für Job-State, Background-Task ruft den existierenden Single-Memo-Service auf. Kein Code-Duplikat.

```
backend/domain/entities/memo_batch_job.py                  ← neue Pydantic-Entity (frozen)
backend/domain/repositories/memo_batch_job_repository.py    ← neuer Port (ABC)
backend/infrastructure/persistence/repositories/memo_batch_job_repository.py  ← SQLA-Adapter
backend/infrastructure/persistence/models/memo_batch_job.py  ← ORM-Model
alembic/versions/0007_memo_batch_jobs.py                    ← Migration

backend/application/services/narrative_service.py
    ↓ erweitert um:
    - start_batch()              # Job erstellen + Background-Task spawnen
    - _execute_batch()           # Background-Worker (private)
    - get_batch_job()            # Status-Abruf mit Stale-Cleanup
    - list_memos_for_run()       # Helper für GET-Response (memo-Liste)

backend/interfaces/rest/routers/memos.py
    ↓ erweitert um:
    - POST /memos/batch          # 202 + Job-ID
    - GET /memos/jobs/{job_id}   # Status + Progress

backend/interfaces/rest/dependencies.py
    ↓ erweitert um:
    - get_memo_batch_job_repository
```

**Wiederverwendung Single-Memo:** Der Background-Worker ruft pro Stock `await self.generate_memo(stock_id, run_id, language)` auf. Cache-Hits, Error-Memo-Persistenz, Schema-Validation — alles wird automatisch ererbt.

**B1-Lehre umgesetzt:** Der Background-Worker öffnet *eigene* DB-Sessions via `session_factory` (analog `SQLAResearchMemoRepository`-Pattern), nicht die Request-Session. `asyncio.gather` ist dann sicher, weil jeder parallele Worker seine isolierte Session nutzt.

---

## 4. Domain & Persistence

> **TL;DR (Reviewer):** Neue Entity `MemoBatchJob` mit 5-Zustände-Lifecycle. Eigene Tabelle `memo_batch_jobs` mit FK auf `ranking_runs`. ORM/Migration-Detail kannst du überfliegen.

### Entity `MemoBatchJob`

```python
class MemoBatchJob(BaseModel):
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

### Status-Lifecycle

| Status | Bedeutung | Übergang nach |
|---|---|---|
| `pending` | Job erstellt, Background-Task noch nicht aktiv | `running` (sofort beim Task-Start) |
| `running` | Background-Worker läuft (`started_at` gesetzt) | `complete` / `partial` / `failed` |
| `complete` | Alle N Memos persistiert (Error-Memos zählen — sind Schema-Fails, in DB) | terminal |
| `partial` | ≥ 1 Stock im `failed_stock_ids` (Network/Timeout) | terminal |
| `failed` | Katastrophischer Fail (alle Sub-Tasks failed, oder stale-cleanup) | terminal |

**Wichtig:** Schema-Validation-Fails (Anthropic liefert kaputtes JSON) werden zu Error-Memos persistiert (Single-Memo-Verhalten) und zählen als "completed". Nur Network/Timeout-Fails landen in `failed_stock_ids` — diese Stocks haben kein Memo in der DB.

### ORM-Tabelle `memo_batch_jobs`

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | UUID | PRIMARY KEY |
| `model_run_id` | UUID | FK → `ranking_runs(id)` ON DELETE CASCADE |
| `top_n` | INTEGER | NOT NULL, CHECK BETWEEN 1 AND 100 |
| `language` | VARCHAR(2) | NOT NULL, CHECK IN ('de', 'en') |
| `status` | VARCHAR(16) | NOT NULL, CHECK IN ('pending','running','complete','partial','failed') |
| `failed_stock_ids` | JSONB | NOT NULL DEFAULT `'[]'::jsonb` |
| `error_message` | TEXT | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `started_at` | TIMESTAMPTZ | NULL |
| `completed_at` | TIMESTAMPTZ | NULL |

Index auf `model_run_id` (für mögliches künftiges "list jobs for run").

UPSERT-Semantik im SQLA-Adapter: `id` und `created_at` sind Lifecycle-Marker und werden bei Konflikt nicht überschrieben (analog `research_memos`).

### Repository-Port

```python
class MemoBatchJobRepository(ABC):
    @abstractmethod
    async def save(self, job: MemoBatchJob) -> None: ...

    @abstractmethod
    async def get(self, job_id: UUID) -> MemoBatchJob | None: ...
```

---

## 5. Service-API

> **TL;DR (Reviewer):** Drei neue Methoden auf `NarrativeService`. `start_batch` returnt sofort, `_execute_batch` läuft im Background mit max 3 parallelen Workern, `get_batch_job` macht Stale-Cleanup beim Lesen. Code-Pattern-Detail kannst du überfliegen.

```python
class NarrativeService:
    # ... bestehende Methoden bleiben unberührt ...

    async def start_batch(
        self,
        model_run_id: UUID,
        *,
        top_n: int = 20,
        language: Literal["de", "en"] = "de",
    ) -> MemoBatchJob:
        """Erstellt Job, validiert Run, spawned Background-Task, returnt sofort."""
        # 1. EN-Guard wie in generate_memo (Single-Memo-Slice §B2)
        # 2. Validate run exists (else LookupError)
        # 3. Estimate cost = top_n × ~$0.025, await CostTracker.check_cap
        # 4. Create MemoBatchJob(status="pending", created_at=now())
        # 5. await self._batch_repo.save(job)
        # 6. asyncio.create_task(self._execute_batch(job.id))   # fire-and-forget
        # 7. return job

    async def _execute_batch(self, job_id: UUID) -> None:
        """Background-Worker. Wird via asyncio.create_task gestartet.

        WICHTIG: Der Worker nutzt KEINE Service-eigenen Repos (die sind an
        die Request-Session des start_batch-Aufrufers gebunden, die längst
        geschlossen ist). Stattdessen baut er pro parallelem Sub-Task seine
        eigenen Repos via session_factory (B1-Lehre).
        """
        # 1. Stage 1 mit isolated session: job laden, status=running setzen,
        #    Run-Results laden, Top-N stocks bestimmen
        # 2. semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCH_WORKERS)  # default 3
        # 3. Stage 2: parallel pro stock, jeder Worker mit isolated session_factory:
        #    async def _one(stock_id):
        #        async with semaphore:
        #            try:
        #                # generate_memo wird mit isolated repos aufgerufen,
        #                # entweder via:
        #                #   a) erweitertes generate_memo(repos=...) — Service-API-Refactor
        #                #   b) neuer private Helper _generate_memo_isolated(...)
        #                # Pattern-Wahl wird im Plan festgelegt.
        #                return ("ok", stock_id, None)
        #            except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
        #                return ("failed", stock_id, str(exc))
        # 4. results = await asyncio.gather(*[_one(s) for s in top_stocks])
        # 5. failed_ids = [s for status, s, _ in results if status == "failed"]
        # 6. status = derive("complete" | "partial" | "failed")
        # 7. update job final, save

    async def get_batch_job(self, job_id: UUID) -> MemoBatchJob | None:
        """Lädt Job; bei status=running mit started_at>10min macht lazy-cleanup auf failed."""
        # Stale-Cleanup-Logik (siehe §8)

    async def list_memos_for_run(
        self,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
    ) -> list[ResearchMemo]:
        """Helper für die GET-Response: alle persistierten Memos für diesen Run."""
        return await self._memo_repo.list_by_run(model_run_id, language=language)
```

**Konfiguration via Settings:**
- `MAX_CONCURRENT_BATCH_WORKERS: int = 3`
- `STALE_BATCH_TIMEOUT_SECONDS: int = 600` (10 min)

**Wichtige Designentscheidungen:**

1. **`asyncio.create_task` statt FastAPI `BackgroundTasks`** — letzteres läuft nach Response im Request-Lifecycle und blockt den Worker. `create_task` läuft unabhängig im Event-Loop.
2. **Eigene DB-Session pro Memo-Generation** (B1-Lehre) — der Worker darf nicht die Request-Session des `start_batch`-Calls nutzen, weil die ist beim Background-Lauf längst geschlossen. `session_factory()` pro Worker macht jeden Memo-Call isoliert.
3. **`asyncio.gather` ist hier sicher**, weil jeder Worker seine eigene Session hat — kein Concurrency-Bug wie in B1.
4. **Network/Timeout-Errors abfangen, alles andere durchlassen** — Schema-Validation-Fails landen als Error-Memos in der DB (existierendes Single-Memo-Verhalten), das ist gewollt.

---

## 6. REST-API + Data-Flow

> **TL;DR (Reviewer):** Zwei Endpoints. POST gibt sofort 202+job_id, GET wird vom Frontend alle 2s gepollt für Live-Progress. Diese Sektion ist für dich zentral — das ist die API die das Frontend nutzt.

### Endpoint 1: `POST /api/v1/memos/batch`

**Request:**
```json
{
  "model_run_id": "uuid-string",
  "top_n": 20,
  "language": "de"
}
```

**Response 202 Accepted:**
```json
{
  "job_id": "uuid-string",
  "model_run_id": "uuid-string",
  "top_n": 20,
  "language": "de",
  "status": "pending",
  "created_at": "2026-05-08T10:30:00Z"
}
```

**Error-Codes:**
- `400 Bad Request`: ungültige `top_n` (Pydantic-Validation)
- `404 Not Found`: `model_run_id` existiert nicht
- `402 Payment Required`: Budget-Cap würde überschritten

### Endpoint 2: `GET /api/v1/memos/jobs/{job_id}`

**Response 200 OK:**
```json
{
  "job_id": "uuid-string",
  "model_run_id": "uuid-string",
  "top_n": 20,
  "language": "de",
  "status": "running",
  "created_at": "2026-05-08T10:30:00Z",
  "started_at": "2026-05-08T10:30:01Z",
  "completed_at": null,
  "progress": {
    "expected": 20,
    "completed": 12,
    "failed": 0
  },
  "failed_stock_ids": [],
  "error_message": null,
  "memos": [
    {
      "stock_id": "uuid-string",
      "ticker": "NESN",
      "one_liner": "Defensiver Quality-Kern mit niedrigem Risiko.",
      "is_error": false
    }
    // ... weitere bisher persistierte Memos
  ]
}
```

**Error-Codes:**
- `404 Not Found`: `job_id` unknown

### Data-Flow

```
Frontend                          Backend
─────────                         ─────────

POST /api/v1/memos/batch
  body: {model_run_id: X, top_n: 20}
                          ────►  start_batch:
                                  1. EN-Guard
                                  2. Run X exists? else 404
                                  3. Cost-Pre-Check (top_n × $0.025)
                                  4. Create job (status=pending), save
                                  5. asyncio.create_task(_execute_batch)
                                  6. return job
                          ◄────  202 + job_id

[Background-Task läuft asynchron:
   _execute_batch(job_id):
     job.status = "running", started_at = now()
     stocks = top 20 from run X
     semaphore = Semaphore(3)
     await asyncio.gather(*[_one(s) for s in stocks])
     final_status = derive
     job.completed_at = now()
]

Frontend pollt alle 2s:
GET /memos/jobs/{job_id}
                          ────►  get_batch_job:
                                  1. job = repo.get(job_id)
                                  2. (lazy stale-cleanup wenn nötig)
                                  3. memos = list_memos_for_run(model_run_id, lang)
                                  4. response = build BatchJobResponse
                          ◄────  200 + {status, progress, memos}

Frontend:
  status === "running" → setTimeout(poll, 2000)
  status terminal → stop polling, render final state
```

**Polling-Intervall:** 2-3s ist gut. Bei Status `running` weiterpollen, bei `complete`/`partial`/`failed` stoppen.

**Frontend-Hinweis:** `progress.completed` / `progress.expected` als Progress-Bar, `memos[]` als Live-Stream. `is_error: true`-Memos können visuell als Error-Card gerendert werden (Badge + grauer Text statt normalem Memo-Layout).

### Bekanntes Limit: `memos[]` ist Run-scoped, nicht Job-scoped

`list_memos_for_run(model_run_id, language)` zieht **alle** persistierten Memos zu diesem Run — auch solche aus vorigen Single-Memo-Calls oder einem parallelen zweiten Batch-Job auf demselben Run (§12 Q4: kein Lock). In dem Fall enthält `memos[]` Einträge, die nicht zu *diesem* Job gehören; `progress.completed = len(memos)` ist dann nicht batch-genau.

Tracking: Issue #86. Mittelfristige Lösung: Spalte `memo_batch_jobs.expected_stock_ids JSONB` + Filter im GET, dann ist `memos[]` strikt Job-scoped.

---

## 7. Cost & Caching

> **TL;DR (Reviewer):** Bei N=20 erwarten wir ~$0.50-0.60 pro Batch. Anthropic-Prompt-Caching gibt uns ~42% Ersparnis ab dem 2. Memo (Smoke-verifiziert in PR #64). Cost-Pre-Check schützt vor Budget-Überschreitung.

### Erwartete Kosten pro Batch

Basis-Annahmen (aus PR #64 Real-API-Smoke):
- Sonnet 4.6: $3/Mtok input, $15/Mtok output
- System-Prompt: ~3300 Tokens (cache-creation cost = $3.75/Mtok = $0.0124, cache-read cost = $0.30/Mtok = $0.001)
- User-Prompt: ~250 Tokens (nicht gecached, neu pro Stock)
- Output: ~900 Tokens / Memo (Tool-Use submit_memo)

| | Input neu | Output | Cache-Creation | Cache-Read | Kosten |
|---|---|---|---|---|---|
| **Memo 1** (cache miss) | 250 | 900 | 3300 | 0 | ~$0.027 |
| **Memo 2-20** (cache hit) | 250 | 900 | 0 | 3300 | ~$0.016 |

**Total für N=20:** $0.027 + 19 × $0.016 = **~$0.33**

Ohne Caching wären's 20 × $0.027 = $0.54 → **~40% Ersparnis** (matcht PR #64-Smoke-Resultat).

### Cost-Pre-Check

Vor Job-Erstellung:
```python
estimated_usd = Decimal(top_n) * Decimal("0.025")  # konservativer Worst-Case-Schätzwert
await self._cost_tracker.check_cap(estimated_usd=estimated_usd)
```

Bei Cap-Überschreitung: `BudgetCapExceededError` → Router mappt zu `402 Payment Required` mit Detail-Message.

### Cost-Logging

Jedes generate_memo-Sub-Call schreibt einen Cost-Log-Eintrag mit `feature="narrative_engine"` (existierendes Behavior). Im Batch-Kontext ist das ausreichend für Cost-Tracking — kein zusätzliches `feature="narrative_batch"` nötig (würde nur den Aggregations-View anders färben).

### Concurrency vs. Cache-Hits

Mit `MAX_CONCURRENT=3` schreiben die ersten 3 Memos parallel ihre Cache-Versionen — eines "gewinnt" und die anderen 2 sind dupliziert. Das kostet ~$0.024 zusätzlich beim Batch-Start. Akzeptabler Trade-off für 3× schnellere Batch-Latenz (10-20s statt 30-60s sequenziell).

Falls Cost-Optimierung wichtiger wird als Latenz: `MAX_CONCURRENT=1` über Settings setzbar.

---

## 8. Error-Handling

> **TL;DR (Reviewer):** Drei Fehlerklassen: Pre-Job (vor 202), Per-Memo (im Worker), Stale-Job (Server-Crash). Best-Effort: einzelne Fails kippen den Batch nicht.

### Pre-Job (vor 202-Response)

| Fehler | HTTP | Verhalten |
|---|---|---|
| `language="en"` | siehe Q6 unten | Service wirft `NotImplementedError` analog Single-Memo (B2). Aktuelles Single-Memo-Router-Verhalten ist 500 (FastAPI-Default). Sollte konsistent gehoben werden — siehe §12 Q6. |
| Run nicht gefunden | 404 Not Found | `LookupError` → Router-Mapping |
| `top_n` < 1 oder > 100 | 400 Bad Request | Pydantic-Validation |
| Budget-Cap exceeded | 402 Payment Required | `CostTracker.check_cap` raises `BudgetCapExceededError` |

### Per-Memo (im Background-Worker)

| Fehler | Quelle | Verhalten |
|---|---|---|
| `anthropic.APITimeoutError` | Call >30s | Stock in `failed_stock_ids`, kein Memo persistiert |
| `anthropic.APIConnectionError` | Network-Fail (DNS, TCP-Reset) | Stock in `failed_stock_ids`, kein Memo persistiert |
| `anthropic.RateLimitError` (429) | Anthropic-Ratelimit | LLMClient retried 3× exponential. Falls weiterhin: in `failed_stock_ids` |
| `pydantic.ValidationError` | Schema-Fail in LLM-Output | Single-Memo-Service persistiert Error-Memo (`model_version="error-fallback"`). Zählt als "completed" — Memo ist in DB, mit Error-Flag |
| `LookupError` (Stock-im-Run-Drift) | Race-Condition | In `failed_stock_ids`, error_message |
| `BudgetCapExceededError` mid-batch | CostTracker (z.B. anderer Service hat Budget verbraucht) | Batch abgebrochen, restliche Stocks in `failed_stock_ids`, status=`partial`, error_message="Budget-Cap erreicht" |

**Status-Aggregation am Batch-Ende:**
```python
n_failed = len(failed_stock_ids)
if n_failed == 0:
    status = "complete"
elif n_failed == top_n:
    status = "failed"
else:
    status = "partial"
```

### Stale-Job (Server-Crash mid-batch)

Wenn der Server während `_execute_batch` crashed/restartet, bleibt der Job in `status="running"` mit `started_at` gesetzt, `completed_at=None`. Der Worker ist tot.

**Lazy-Cleanup beim GET:**
```python
async def get_batch_job(self, job_id):
    job = await self._batch_repo.get(job_id)
    if job and job.status == "running" and job.started_at is not None:
        elapsed = (datetime.now(tz=UTC) - job.started_at).total_seconds()
        if elapsed > STALE_BATCH_TIMEOUT_SECONDS:  # default 600s = 10min
            stale_job = job.model_copy(update={
                "status": "failed",
                "completed_at": datetime.now(tz=UTC),
                "error_message": "Job stale — Server-Restart oder Crash während Ausführung",
            })
            await self._batch_repo.save(stale_job)
            return stale_job
    return job
```

Bei N=20 + 3-concurrent + ~3s/Memo erwartet ~20s Laufzeit. 10min Timeout ist sicher Stale-Marker ohne false-positives.

### Bekanntes Limit: Background-Task überlebt `SIGTERM` nicht

`asyncio.create_task(self._execute_batch(...))` ist an den FastAPI-Worker-Event-Loop gebunden. Bei einem `SIGTERM` während eines laufenden Batches (Render-Deploy, Auto-Restart) wird der Task ohne `await` gecancelt → Job bleibt in `running`, wird erst nach `STALE_BATCH_TIMEOUT_SECONDS` (10 min) via Lazy-Cleanup auf `failed` markiert.

Für die Capstone-Demo akzeptabel. Tracking: Issue #87. Saubere Lösung: FastAPI-`lifespan`-Shutdown-Hook, der pending Tasks mit `error_message="server shutdown"` als `failed` markiert.

### Logging

Pro Batch:
- `INFO` bei `start_batch`: `"Batch %s started: run=%s, top_n=%d"`
- `INFO` bei `_execute_batch` Begin: `"Batch %s running: %d stocks"`
- `WARNING` pro Memo-Fail: `"Batch %s memo failed for stock %s: %s"`
- `INFO` bei Batch-Ende: `"Batch %s %s: %d ok, %d failed"`

---

## 9. Test-Strategie

> **TL;DR (Reviewer):** Unit + Integration + E2E mit Stub-Anthropic. Coverage-Ziel ≥90% auf neuen Code. Detail kannst du überfliegen.

### Unit (mit Mocks, kein Netzwerk, in CI)

- `start_batch`-Logik (Validierung, Job-Erstellung, Task-Spawn)
- `_execute_batch`-Status-Übergänge (complete / partial / failed)
- Stale-Cleanup-Logik
- Concurrency-Limit (Semaphore-Mock zählt parallele Worker)
- Schema-Validation für `MemoBatchJob`-Entity
- ORM-Roundtrip (frozen, FK, CHECK-Constraints)

### Integration (PG, in CI)

- `SQLAMemoBatchJobRepository.save/get`-Roundtrip
- UPSERT-Semantik: id und created_at als Lifecycle-Marker
- `failed_stock_ids` JSONB-Roundtrip
- Concurrent saves via session_factory (B1-Lehre)

### E2E (PG + StubAnthropic, in CI)

- POST /batch → 202 + job_id
- GET /jobs/{id} während running → `running` + progress.completed wächst
- GET /jobs/{id} nach Abschluss → `complete` + alle Memos in `memos[]`
- 404-Pfade (unknown run, unknown job_id)
- Cost-Cap-Pfad (mock CostTracker raises → 402)
- Partial-Failure (eine APITimeoutError gemockt → status=partial)

### Coverage-Ziel

≥ 90% auf neuen Code (`narrative_service` Batch-Methoden, `memo_batch_job` Entity/Repo/ORM). Smoke-Test gegen echte Anthropic-API einmal manuell verifiziert wie in Single-Memo-Slice (siehe §10 Acceptance).

---

## 10. Akzeptanz-Kriterien

> **TL;DR (Reviewer):** Was muss vor dem Merge erfüllt sein.

- [ ] Alle Unit + Integration + E2E Tests grün
- [ ] Coverage ≥ 90% auf neuen Code
- [ ] mypy strict + ruff format/check clean
- [ ] **Real-API-Smoke** einmal manuell ausgeführt (Skript `scripts/smoke_narrative_batch_real_api.py`):
  - POST /batch mit top_n=3 (kleiner Batch zur Cost-Kontrolle)
  - Polling /jobs/{id} bis status=complete
  - Verifiziert: 3 Memos in DB, cache_read_input_tokens > 0 ab Memo 2, Cost-Log-Einträge geschrieben
- [ ] AI-USAGE.md-Eintrag mit Reflexion über Plan-Code-Drifts und Lerneffekten
- [ ] Spec §11.1 ergänzt falls Plan-Code-Drift in der Implementation entdeckt wird

---

## 11. Bewusste Abweichungen von Parent-Spec

> **TL;DR (Reviewer):** Wo wir vom `2026-04-28-narrative-engine.md`-Parent abweichen und warum.

| Parent-Spec | Slice-Verhalten | Begründung |
|---|---|---|
| §8 — Synchroner Batch-Call mit "Progress-Response" | Async-Job mit Polling | Sync HTTP für 30-60s ist fragil (Netzwerk-Hiccup, Browser-Timeout). Async-Job + Polling ist Standard-Pattern für Long-Running. |
| §8 — `batch_generate_memos` als zweiter Service-API-Methode | `start_batch` + `_execute_batch` (private) | Zwei Phasen: Validate+Job-Erstellung sync, Generation async. Nicht in eine Methode pressbar. |
| §13 Q3 — "Wie hoch ist der Concurrency-Limit?" | Default 3, konfigurierbar | Spec hatte das offen. 3 = pragmatisch (Anthropic-Ratelimit + Cache-Hit-Trade-off). |
| §11 — Webhook bei Batch-Ende | nicht im Slice | Out-of-scope, Frontend pollt. Folge-PR wenn UX-Anforderung kommt. |

### 11.1 Plan-Code-Drift

Gefunden während der 12 Build-Steps durch Two-Stage-Review (Spec-Reviewer + Code-Quality-Reviewer pro Task).

| Plan-Annahme | Code-Realität | Fix-Commit |
|---|---|---|
| `down_revision="0005_research_memos"` | Echte revision-id ist nur `"0005"` (alembic generiert kurze IDs, keine Langnamen) | Task 3 (Subagent fand bei alembic-Inspektion) |
| `server_default="[]"` für JSONB-Spalte (`failed_stock_ids`) | Invalid PG syntax — PostgreSQL erwartet SQL-Literal (`'[]'::jsonb`). Fix: `default=list` (Python-side default) statt `server_default` | Task 3 review-fix |
| Index nur in Migration definiert | ORM braucht Index auch in `__table_args__` für autogenerate-Drift-Detection (sonst erzeugt `alembic revision --autogenerate` jedes Mal einen Schein-Drift) | Task 3 review-fix |
| Test mit `uuid.uuid4()` direkt als `stock_id` in `research_memos` | FK-Violation — `research_memos` hat FK auf `stocks(id)`. Ohne vorherigen Stock-Insert schlägt jedes INSERT fehl | Task 5 review-fix (3 Stocks in `conftest.py` vor-seeden) |
| `_execute_batch` catched nur `APITimeoutError` + `APIConnectionError` | Spec §8 listet `RateLimitError` als handled — nach LLMClient-Retry-Exhaustion bubbled das uncaught und crashte den Worker-Task | Task 8 review-fix |
| `ticker: str = ""` Placeholder in Job-Response | Semantisch unsauber — leerer String ist nicht "unbekannt". `str \| None = None` korrekter bis Task 11 ticker-Lookup aus DB implementiert | Task 10 review-fix |
| Inline-imports in `_execute_batch` für SQLA-Repos (Plan hatte lokale Import-Blöcke) | Module-level imports sind cleaner für Mocking in Tests (lokale Imports umgehen `unittest.mock.patch`) | Task 8 implementation-decision |

**Offenes Issue (nicht in diesem Slice gefixt):** `BudgetCapExceeded`-Global-Exception-Handler gibt HTTP 503 zurück. Spec §6 sagt 402 für `/memos/batch`. Die Per-route `HTTPException(402)`-Behandlung im Batch-Endpoint ist korrekt, aber der globale Handler bleibt inkonsistent (würde 503 für andere Routen returnen, die BudgetCapExceeded nicht explizit fangen). Folge-Issue zur Konsolidierung — beide Memo-Endpoints (`/memos/generate` + `/memos/batch`) sollten konsistent 402 returnen, globaler Handler entweder entfernen oder auf 402 heben.

---

## 12. Offene Entscheidungen

> **TL;DR (Reviewer):** Was wir während Spec-Schreibung NICHT entschieden haben — wird bei Implementation geklärt oder bleibt für Folge-PR.

| # | Frage | Aktueller Plan | Wann entschieden? |
|---|---|---|---|
| Q1 | Auto-Cleanup alter Jobs (z.B. nach 30 Tagen)? | Nicht implementieren — DB-Volumen ist klein, Folge-PR wenn problematisch | Bei Bedarf, frühestens nach 1. Demo-Lauf |
| Q2 | Cancel-Funktionalität für laufende Jobs? | Nicht implementieren — wenn der User abbrechen will, kann er einfach weiter andere Tasks machen, der Batch läuft auf Anthropic-Seite eh durch | Bei Bedarf |
| Q3 | Anthropic Message Batches API (50% Discount)? | Nicht — 24h-SLA passt nicht zum Demo-Use-Case | Bei Production-Cost-Druck neu evaluieren |
| Q4 | Mehrere parallele Jobs pro Run erlauben oder Lock? | Erlauben (kein Lock) — Cache dedupliziert die Anthropic-Calls, harmless | Bei Implementation final entscheiden |
| Q5 | Polling-Intervall fest oder konfigurierbar? | Frontend-Detail, im Backend irrelevant | Frontend-Spec |
| Q6 | EN-Guard HTTP-Code: 500 (aktueller Single-Memo) oder 501 Not Implemented? | Konsistent mit Single-Memo lassen (500 default). Bei Folge-PR beide Router auf 501 mit explizitem `HTTPException` heben — gehört zu W3 (`is_error`-Cleanup, Issue #67) oder eigenes kleines Issue | Bei Implementation final entscheiden, oder als kleines Folge-Issue tracken |

---

## 13. Änderungshistorie

| Version | Datum | Autor | Änderung |
|---|---|---|---|
| Draft v1.0 | 2026-05-08 | Sheyla / Claude Code Opus 4.7 | Initiale Slice-Spec — schneidet Multi-Memo-Batch aus Parent-Spec heraus. Async-Job-Pattern mit Polling. Erstes Async-Job-Pattern im Repo, Vorbild für künftige Long-Running-Tasks. |
