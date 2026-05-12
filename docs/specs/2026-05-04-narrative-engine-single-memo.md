# Spec: Narrative Engine — Single-Memo Slice (Layer 1, Teil 2 von N)

**Status**: Draft v1.0 — 2026-05-04
**Rolle**: B — AI Engineer (Sheyla)
**Parent-Spec**: `docs/specs/2026-04-28-narrative-engine.md`
**Vorgänger-Slice**: `docs/specs/2026-04-30-narrative-engine-foundation.md` (Schema, Entity, Repository — gemerged via PR #54)

---

## 1. Zweck

Diese Spec schneidet einen **implementierbaren Slice** aus der Parent-Spec heraus: der **Single-Memo-Pfad** Ende-zu-Ende, von einem REST-Aufruf bis zum persistierten `ResearchMemo`. Batch-Generierung, dedizierter Regenerate-Endpoint, Golden-Prompt-CI und Admin-Usage-Endpoint bleiben für Folge-PRs.

Begründung der Slicing-Wahl: ein einzelner Memo-Pfad validiert das Pydantic-Schema, das Prompt-Caching, die Tool-use-Strukturierung und den Error-Memo-Pfad **vollständig**. Batch ist danach ein dünner Wrapper (Semaphore + Sammelaufruf) und braucht keine eigene Architektur-Diskussion.

---

## 2. Scope

### In Scope

- `NarrativeService` mit zwei Methoden: `generate_memo` und `get_memo`
- Prompt-Templates DE (System + User) als Jinja2-Files
- `PromptTemplateLoader` (Jinja2, einmal beim App-Start geladen)
- Strukturierter Output via **Anthropic Tool-Use** (`tool_choice` erzwingt das `submit_memo`-Tool)
- Prompt-Caching auf System-Prompt-Block via `cache_control: ephemeral`
- `LLMClient`-Erweiterung: `system`-Parameter akzeptiert zusätzlich `list[dict[str, Any]]` für content-blocks-mit-cache_control
- 2 REST-Endpoints: `POST /api/v1/memos/generate`, `GET /api/v1/memos/{stock_id}/{run_id}`
- Error-Memo-Persistierung bei LLM-Malformed-Output (kein App-Crash)
- 3 Fixture-basierte Integration-Tests + Cache-Hit-Smoke-Test
- Sample-Memo unter `docs/examples/research-memo-sample.json`
- AI-USAGE.md-Eintrag mit beobachteter Cache-Hit-Rate

### Out of Scope (Folge-PRs)

- `batch_generate_memos` + `POST /api/v1/memos/batch`
- Dedizierter `POST /api/v1/memos/{stock_id}/{run_id}/regenerate`-Endpoint
- Englisches Prompt-Template (Stub-File mit TODO-Kommentar wird angelegt — Architektur-Vorbereitung, kein Inhalt)
- Golden-Prompt-Workflow gegen echte Anthropic-API (`.github/workflows/llm-smoke.yml`)
- LLM-as-Judge-Bewertung
- `GET /admin/llm-usage`-Endpoint (existierender `CostTracker` reicht für jetzt)
- Restliche 2 Fixtures aus Parent-Spec §10.2 (`contradictory_trend_value`, `ambiguous_stock`)

---

## 3. Architektur

### Dateistruktur

```
backend/
├── application/services/
│   └── narrative_service.py                    # NEU (enthält UniverseContext-Value-Object inline)
├── domain/repositories/
│   └── stock_repository.py                     # ERWEITERT (get(stock_id) hinzugefügt)
├── infrastructure/persistence/repositories/
│   └── stock_repository.py                     # ERWEITERT (get(stock_id) Adapter)
├── infrastructure/llm/
│   ├── client.py                               # MINI-EXT (system: str | list[dict])
│   ├── prompts/
│   │   ├── __init__.py                         # NEU
│   │   ├── prompt_loader.py                    # NEU
│   │   ├── narrative_system.de.md.j2           # NEU (DE-Inhalt)
│   │   ├── narrative_system.en.md.j2           # NEU (Stub mit TODO)
│   │   └── narrative_user.md.j2                # NEU (sprach-neutral, Daten-Slots)
└── interfaces/rest/
    ├── routers/memos.py                        # NEU
    └── app.py                                  # ERWEITERT (Router registrieren)
```

### Komponenten-Verantwortung

| Komponente | Verantwortung | Tests |
|---|---|---|
| `PromptTemplateLoader` | Jinja2-Environment, `render(template_name, ctx) -> str`. Templates beim App-Start geladen, nicht pro Request. | Unit (Snapshot) |
| `NarrativeService` | Orchestriert Cache-Check → Daten laden → Prompt rendern → LLM-Call → Schema-validieren → Persistieren. Enthält `UniverseContext` Pydantic-Value-Object als private Klasse (nur 1 Consumer im MVP). | Unit + Integration |
| `LLMClient` (erweitert) | Akzeptiert `system: str \| list[dict[str, Any]] \| None`. Cost-Estimator versteht beide Fälle. | Unit |
| `StockRepository` (erweitert) | Neue Methode `get(stock_id: UUID) -> Stock \| None`. Adapter-Implementation analog zu `get_by_ticker`. | Unit (Adapter-Test) |
| `memos.py`-Router | 2 Endpoints, FastAPI-DI für Service-Injection, Pydantic-Request/Response-Schemas. | Integration |

---

## 4. Data Flow

```
POST /api/v1/memos/generate { stock_id, model_run_id }
  │
  ▼
NarrativeService.generate_memo(stock_id, run_id, lang="de", force_regenerate=False)
  │
  ├─ 1. memo_repo.get(stock_id, run_id)
  │       └─ wenn vorhanden + nicht force → return existing (0 Kosten, kein LLM-Call)
  │
  ├─ 2. Daten laden (parallel via asyncio.gather):
  │       stock_repo.get(stock_id)                  → Stock          (404 wenn None)
  │       run_repo.get_results(run_id)              → list[dict]     (404 wenn None)
  │
  │     Aus dem dict-list im Service ableiten (kein neuer Port nötig):
  │       a. ranking_dict = next(r for r in results if r["ticker"] == stock.ticker)
  │          → enthält total_rank, weighted_avg, is_sweet_spot, per_model_ranks
  │          → 404 wenn der Stock nicht im Run drin ist
  │       b. universe_context = UniverseContext(
  │            n_stocks=len(results),
  │            median_rank=median(r["total_rank"] for r in results),
  │            top20_threshold=quantile([r["total_rank"] for r in results], 0.20),
  │          )
  │
  ├─ 3. system_prompt = prompt_loader.render("narrative_system.de.md.j2", static_ctx)
  │     user_prompt   = prompt_loader.render("narrative_user.md.j2",       dynamic_ctx)
  │
  ├─ 4. response = llm_client.messages_create(
  │       model="claude-sonnet-4-6",
  │       system=[{"type":"text","text":system_prompt,"cache_control":{"type":"ephemeral"}}],
  │       messages=[{"role":"user","content":user_prompt}],
  │       tools=[{"name":"submit_memo","input_schema":ResearchMemoSchema.model_json_schema()}],
  │       tool_choice={"type":"tool","name":"submit_memo"},
  │       feature="narrative_engine",
  │       max_tokens=2000,
  │     )
  │
  ├─ 5. tool_call = next(b for b in response.content if b.type == "tool_use")
  │     try:
  │       memo_schema = ResearchMemoSchema.model_validate(tool_call.input)
  │     except (ValidationError, StopIteration) as exc:
  │       → log + dump raw response zu logs/malformed_memos/{run_id}_{stock_id}_{ts}.json
  │       → memo_schema = _build_error_memo_schema(stock, total_rank, exc)
  │
  ├─ 6. memo_entity = ResearchMemo.from_schema(memo_schema, stock_id, run_id, model_version, lang)
  │     await memo_repo.save(memo_entity)   # UPSERT (Repository macht on_conflict_do_update)
  │
  └─ return memo_entity
```

### Sequenz `get_memo`

```
GET /api/v1/memos/{stock_id}/{run_id}
  │
  ▼
memo_repo.get(stock_id, run_id)
  ├─ vorhanden  → 200 + Memo-DTO
  └─ None       → 404
```

---

## 5. Service-API

```python
# backend/application/services/narrative_service.py

class NarrativeService:
    def __init__(
        self,
        *,
        memo_repository: ResearchMemoRepository,
        run_repository: RankingRunRepository,
        stock_repository: StockRepository,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
        model: str = "claude-sonnet-4-6",
    ) -> None: ...

    async def generate_memo(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        *,
        lang: Literal["de"] = "de",  # "en" architektonisch vorbereitet, MVP nur "de"
        force_regenerate: bool = False,
    ) -> ResearchMemo: ...

    async def get_memo(
        self,
        stock_id: UUID,
        model_run_id: UUID,
    ) -> ResearchMemo | None: ...
```

`force_regenerate=True` ist im Service implementiert, aber im REST-Slice **nicht** als eigener Endpoint exposed. Mechanismus für manuelles Re-Generate: HTTP-Layer-Erweiterung im Folge-PR via `?force=true`-Query oder dedizierten POST.

---

## 6. REST-Endpoints

### `POST /api/v1/memos/generate`

```jsonc
// Request
{
  "stock_id": "550e8400-e29b-41d4-a716-446655440000",
  "model_run_id": "550e8400-e29b-41d4-a716-446655440001"
}

// 200 Response — neu generiert ODER aus Cache
{
  "id": "...",
  "stock_id": "...",
  "model_run_id": "...",
  "language": "de",
  "memo": { /* ResearchMemoSchema */ },
  "model_version": "claude-sonnet-4-6",
  "created_at": "2026-05-04T...",
  "updated_at": "2026-05-04T...",
  "is_error": false
}
```

**Status-Codes**:
- `200`: Memo erfolgreich generiert oder aus Cache geliefert (auch error-memo)
- `404`: Stock oder ModelRun existiert nicht
- `503`: Budget-Cap erreicht (`BudgetCapExceededError`)
- `504`: Anthropic-Timeout nach Retry

### `GET /api/v1/memos/{stock_id}/{run_id}`

- `200`: Memo vorhanden (gleiche Response-Shape wie POST)
- `404`: kein Memo vorhanden

### Hinweis Pydantic-Response-Schema

`is_error: bool` ist im Response-DTO explizit (nicht im Domain-Schema) — leitet sich ab aus `confidence == "low"` UND `one_liner` beginnt mit "Memo-Generierung fehlgeschlagen". Frontend kann darauf rendern.

---

## 7. Error-Handling

| Fehlerart | Erkennung | Reaktion |
|---|---|---|
| Stock/Run/Ranking fehlt | DB-Query liefert `None` | 404, kein LLM-Call |
| `BudgetCapExceededError` | `cost_tracker.check_cap()` raised | 503, bestehender Mechanismus |
| Anthropic 429 | SDK-Default-Retry | Transparent, `max_retries=3` im Client-Konstruktor |
| Anthropic Timeout | `timeout=30.0` im SDK-Call | 1× Retry mit 60s, dann `LLMTimeoutError` → 504 |
| Tool-Use-Block fehlt / falscher Tool-Name | `next(...)` wirft `StopIteration` | Error-Memo-Pfad |
| Pydantic-`ValidationError` auf `tool_call.input` | Validation in Schritt 5 | Error-Memo-Pfad |
| DB-Constraint-Verletzung beim Save | Repo wirft `IntegrityError` | Bubble up als 500 — deutet auf Bug hin |

### Error-Memo-Pfad

Bei Tool-Use-Fehlschlag oder Pydantic-Fail:

1. Raw-Response (vollständiges `response.model_dump()`) wird in `logs/malformed_memos/{run_id}_{stock_id}_{unix_ts}.json` geschrieben (mkdir-p, atomic-write).
2. Ein **error-memo** wird konstruiert:
   ```python
   ResearchMemoSchema(
       ticker=stock.ticker,
       total_rank=total_rank.rank,
       one_liner="Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
       ranking_interpretation=f"Automatisch generiertes Memo nicht erzeugbar (Fehler: {exc.__class__.__name__}). Siehe Logs unter logs/malformed_memos/.",
       sweet_spot=False,
       sweet_spot_explanation=None,
       contradictions=[],
       key_strengths=["—"],
       key_risks=["—"],
       confidence="low",
       generated_at=datetime.now(UTC),
       model_version="error-fallback",
   )
   ```
3. Dieses error-memo wird via Repository persistiert.
4. REST gibt `200` mit `is_error=true`. Frontend muss das im Endgame rendern.

`MalformedMemoError` als neue domain-Exception ist **nicht** nötig — der Pfad wird intern abgefangen, nicht propagiert. (Spec-Treue Abweichung von Sektion-3-Diskussion oben: weniger Code, gleicher Outcome.)

---

## 8. Prompt-Caching

System-Prompt + Tool-Definition sind beim Single-Memo-Pfad pro Process konstant. Der Cache-Hit zeigt sich also nur, wenn **mehrere Calls innerhalb von 5 Minuten** abgesetzt werden.

### Cache-Block-Struktur

```python
system=[
    {
        "type": "text",
        "text": system_prompt_de,
        "cache_control": {"type": "ephemeral"}
    }
]
```

**Tool-Definition wird automatisch mit-gecached**, weil der Anthropic-Cache-Algorithmus den gesamten Prefix bis zum letzten Cache-Breakpoint cached.

### Beobachtbarkeit

Bei jedem Call gibt die Anthropic-Response `usage.cache_creation_input_tokens` und `usage.cache_read_input_tokens` zurück. Erster Schritt im Implementations-Plan: prüfen, ob `CostTracker.record()` diese Felder bereits erfasst. Falls nein, kleine Erweiterung mit eigenem Build-Step im Plan, bevor der Service gebaut wird.

### Verifikation in CI

Cache-Hit-Verhalten ist nicht in CI gegen die echte API testbar. Stattdessen: `StubAnthropicClient` zählt mit, dass System-Block-Identity zwischen 2 sequentiellen Calls gleich ist. Smoke-Test, dass der Code-Pfad nicht aus Versehen den System-Prompt mutiert.

---

## 9. Test-Strategie

### 9.1 Unit (`backend/tests/unit/`)

| Datei | Was getestet wird |
|---|---|
| `test_prompt_loader.py` | Jinja2-Rendering deterministisch, Snapshot gegen `tests/fixtures/prompts/expected_user_prompt.md` |
| `test_narrative_service.py` | 5 Pfade mit Mock-`LLMClient`: cache-hit, happy, stock-fehlt-404, tool-use-leer-→-error-memo, pydantic-fail-→-error-memo |
| `test_llm_client_system_block.py` | Erweiterung: `system: list[dict]` → SDK-Forwarding korrekt; Cost-Estimation iteriert über alle text-blocks |
| `test_memos_router.py` (lightweight) | Pydantic-Request/Response-Schemas validieren |

### 9.2 Integration (`backend/tests/integration/`)

| Datei | Fixtures | Was getestet wird |
|---|---|---|
| `test_narrative_service_integration.py` | `top_quality_stock.json`, `contradictory_quality_risk.json`, `malformed_response.json` | Service gegen echte PG (Testcontainers) + StubAnthropicClient. Schema-Validation, DB-Persistenz, Error-Memo-Pfad |
| `test_memos_router_e2e.py` | Wie oben | FastAPI-TestClient: POST happy, POST cached, GET hit, GET miss-404 |
| `test_prompt_caching_smoke.py` | — | 2 sequentielle `generate_memo`-Calls, StubAnthropicClient verifiziert System-Block-Identity zwischen Calls |

### 9.3 Coverage-Ziele

- Unit: ≥90%
- Integration: ≥80%
- Gesamt: ≥85%

### 9.4 StubAnthropicClient

Lebt unter `backend/tests/fixtures/llm/stub_anthropic_client.py`. Lädt JSON-Fixture beim Konstruktor, erwartet `messages_create`-Aufruf mit beliebigen Args, gibt fixture-basierte Response zurück. Unterstützt Multi-Call-Sequenz (Liste von Fixtures).

---

## 10. Akzeptanz-Kriterien

Implementation dieser Slice ist komplett, wenn:

- [ ] `StockRepository.get(stock_id: UUID) -> Stock | None` als neue abstract-Methode + SQLA-Adapter-Implementation
- [ ] `PromptTemplateLoader` (Jinja2) in `backend/infrastructure/llm/prompts/prompt_loader.py`
- [ ] `narrative_system.de.md.j2` ausgefüllt mit Inhalt aus Parent-Spec §5.1 (Rollen-Definition, Modell-Beschreibungen, Sweet-Spot-Definition, Interpretations-Regeln, Ton, Disclaimer, Output-Format-Hinweis, 1× Few-Shot)
- [ ] `narrative_system.en.md.j2` als Stub-Datei mit TODO-Kommentar
- [ ] `narrative_user.md.j2` ausgefüllt nach Parent-Spec §5.2
- [ ] `LLMClient.messages_create` akzeptiert `system: str | list[dict[str, Any]] | None`; `_estimate_messages_cost` iteriert korrekt
- [ ] `NarrativeService.generate_memo` und `.get_memo` wie in §5
- [ ] `POST /api/v1/memos/generate` und `GET /api/v1/memos/{stock_id}/{run_id}` live, in OpenAPI-Schema sichtbar
- [ ] Error-Memo wird bei Tool-Use-Fehlschlag oder Pydantic-Fail in DB persistiert + Raw-Response in `logs/malformed_memos/`
- [ ] Alle Tests aus §9.1 und §9.2 grün
- [ ] Coverage: Unit ≥90%, Integration ≥80%, Gesamt ≥85%
- [ ] `docs/examples/research-memo-sample.json` mit einem realistischen Beispiel
- [ ] AI-USAGE.md-Eintrag inkl. Cache-Hit-Rate aus mind. einem manuellen 2-Call-Smoke-Test
- [ ] mypy strict + ruff durchgehend clean
- [ ] Sample-Run gegen echte Anthropic-API einmal manuell verifiziert (nicht in CI)

---

## 11. Bewusste Abweichungen von Parent-Spec

| Parent-Spec-Stelle | Slice-Verhalten | Begründung |
|---|---|---|
| §8 — `batch_generate_memos` | nicht im Slice | Out-of-scope, Folge-PR |
| §8 — Regenerate-Endpoint | nicht im Slice | Out-of-scope, Folge-PR |
| §9 — `MalformedMemoError` | nicht eingeführt; intern abgefangen | Weniger Code, gleicher Outcome |
| §10.2 — 5 Fixtures | nur 3 Fixtures | Die 3 decken alle Code-Pfade ab; restliche 2 sind redundant |
| §10.3 — Golden-Prompt-CI | nicht im Slice | Out-of-scope, Folge-PR |
| §11 — `/admin/llm-usage` | nicht im Slice | Existierender `CostTracker` reicht |
| §13 Q1, Q2, Q4, Q5, Q6 | nicht entschieden | Q1/Q4 N/A in Slice (kein Batch); Q2/Q5/Q6 für Folge-PR |
| §5 / §8 Parent — Parameter `lang` | Code verwendet `language` (Service, Router, Entity, ORM, Repository) | `language` ist semantisch klarer und weniger kollisionsanfällig (`lang` kollidiert mit Python-`builtins`-Konvention sowie HTML-Attribut-Namen). Konsistent über alle Layer durchgezogen. Parent-Spec wird in Folge-Slice harmonisiert (Issue offen bei nächster Master-Spec-Revision). itsFabia W2 in PR #64. |

### 11.1 Plan-Code-Drift (nach PR #64 Review von itsFabia)

Drei Stellen, an denen die Implementierung von der Slice-Spec abwich und im Review-Fix-Bundle korrigiert wurden:

| Spec-Forderung | Drift im Plan/Code | Fix-Commit |
|---|---|---|
| §4 — sequenzielle Daten-Loads (`stock` dann `results`) | `asyncio.gather` mit geteilter `AsyncSession` (Concurrency-Bug) | B1 — `feat/narrative-single-memo` |
| §2 + §5 — Slice ist DE-only, EN-Template ist Stub | Service akzeptierte `language="en"` ohne Guard → Anthropic-Call mit 1-Wort-Prompt → Token-Verbrauch | B2 — Service raised `NotImplementedError` |
| §5 — `generate_memo` returnt persistierten Memo (mit DB-vergebener `id`/`created_at`) | Service returnte in-memory Entity mit frischer `uuid4()` → Drift gegenüber DB-Row bei `force_regenerate=True` | B3 — Reload via `memo_repo.get()` nach `save()` |

Lehre für Folge-PRs: Plan-Pseudo-Code muss vor Code-Generierung gegen DI-Wiring (geteilte Sessions) und Repository-Vertrag (UPSERT-Semantik) geprüft werden. Reality-Check (v1.0 → v1.1) erkannte fehlende Repo-Methoden, aber nicht die Concurrency-Implikation der Session-Teilung.

---

## 12. Änderungshistorie

| Version | Datum | Autor | Änderung |
|---|---|---|---|
| Draft v1.0 | 2026-05-04 | Sheyla / Claude Code Opus 4.7 | Initiale Slice-Spec — schneidet Single-Memo-Pfad aus Parent-Spec heraus |
| Draft v1.1 | 2026-05-04 | Sheyla / Claude Code Opus 4.7 | Realitäts-Korrektur vor Plan-Schreiben: Spec referenzierte nicht-existente Repo-Methoden (`stock_repo.get`, `ranking_repo.get_for_stock`, `ranking_repo.get_universe_context`). Korrigiert: `StockRepository.get` als kleine Erweiterung; ranking + universe context werden inline aus `RankingRunRepository.get_results()` abgeleitet (kein neuer Port). `UniverseContext` ist Service-internes Value-Object, nicht eigene Datei. |
| Draft v1.2 | 2026-05-08 | Sheyla / Claude Code Opus 4.7 | §11.1 ergänzt: Plan-Code-Drift-Tabelle für die drei Blocker aus PR #64 Review (B1 asyncio.gather, B2 EN-Template-Guard, B3 ID-Reload). Spec selbst unverändert — die Drift war Plan→Code, nicht Spec→Plan. |
| Draft v1.3 | 2026-05-10 | Sheyla / Claude Code Opus 4.7 | §11 ergänzt: bewusste Parameter-Umbenennung `lang` → `language` (itsFabia W2 in PR #64). Doku-Only — Code unverändert, Begründung nachgezogen. Parent-Spec-Harmonisierung in Folge-Slice. |
