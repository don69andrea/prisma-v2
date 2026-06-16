> **Status-Update 13. Juni 2026, ~17:00:** Seit Erstellung dieses Dokuments wurden
> 12 von 21 Tasks abgeschlossen (7 Cleanup-PRs merged, viele Features waren bereits
> implementiert). Aktuelle Arbeit: T8, T17, T19, T20 in Bearbeitung.

# AGENT CONTEXT — PRISMA V2

> Dieses Dokument gibt einem neu gestarteten Claude-Code-Agenten den vollständigen Kontext
> über Architektur, offene Aufgaben und Konventionen. Beim Start einer neuen Session immer
> zuerst dieses Dokument lesen.

---

## §1 · PROJEKT-ÜBERSICHT

**PRISMA V2** ist eine Full-Stack Aktienanalyse-Plattform für den Schweizer Markt.
Sie kombiniert ML-Ranking, konversationelle Discovery, Memo-Generierung und Portfolio-Simulation.

- **Frontend:** Next.js 14 (App Router), TypeScript, TailwindCSS
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL + pgvector
- **ML:** scikit-learn, SHAP, Monte Carlo Simulation
- **LLM:** Claude (Anthropic) — Haiku für Klassifikation, Sonnet für Memos/Research
- **Deployment:** Render.com (Monorepo)

---

## §2 · VERZEICHNISSTRUKTUR

```
prisma-v2/
├── frontend/               # Next.js App
│   ├── app/                # App Router Pages & Layouts
│   ├── components/         # Shared UI Components
│   ├── lib/api/            # API Client Functions
│   └── e2e/                # Playwright E2E Tests
├── backend/                # FastAPI App
│   ├── application/
│   │   └── services/       # Business Logic (Application Layer)
│   ├── domain/             # Domain Models & Repository Interfaces
│   ├── infrastructure/     # DB-Adapter, Repositories, LLM-Clients
│   ├── interfaces/rest/    # FastAPI Routers, Schemas, Middleware
│   └── tests/              # Unit & Integration Tests
└── docs/                   # Dokumentation
```

---

## §3 · ARCHITEKTUR-PRINZIPIEN

1. **Hexagonale Architektur:** Domain ← Application ← Infrastructure/Interface
2. **Async-first:** Alle I/O-Operationen mit `async/await`; blocking I/O via `asyncio.to_thread()`
3. **Repository Pattern:** Alle DB-Zugriffe über Repository-Interfaces
4. **FastAPI Dependency Injection:** Services via `Depends()` injiziert
5. **TDD-Pflicht:** Unit-Tests vor oder zusammen mit Implementierung

---

## §4 · BRANCH-WORKFLOW

```
main          ← Produktions-Branch (PR required)
develop       ← Integration-Branch
feature/xxx   ← Feature-Branches (von develop)
bugfix/xxx    ← Bugfix-Branches (von develop)
chore/xxx     ← Maintenance (Docs, Config)
```

---

## §5 · CODING-KONVENTIONEN

- Python: `snake_case`, Pydantic v2 Models, `async def` für alle Services
- TypeScript: `camelCase`, `PascalCase` für Components, strict mode
- Commits: Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`)
- Tests: pytest mit `pytest-asyncio`, Playwright für E2E

---

## §6 · WICHTIGE DATEIEN

| Datei | Zweck |
|-------|-------|
| `CLAUDE.md` | Projektstatus-Tabelle (DONE/PARTIAL/NEXT) |
| `AGENTS.md` | Coding-Konventionen, Branch-Workflow |
| `docs/OPEN_ITEMS.md` | Planungsdokument mit offenen Tasks |
| `backend/interfaces/rest/app.py` | FastAPI App-Initialisierung & Router-Mounting |
| `backend/application/services/` | Alle Business-Logic Services |
| `frontend/lib/api/` | Alle Frontend API-Client Funktionen |

---

## §7 · KRITISCHE BUGS

| ID | Beschreibung | Status |
|----|-------------|--------|
| BUG-1 | Portfolio Simulator — `SimulatorClient.tsx` fehlte | ✅ ERLEDIGT |
| BUG-2 | Discovery Legacy-Endpoints statt `/api/v1/discovery/*` | ✅ ERLEDIGT |
| BUG-3 | Memo-Button permanent deaktiviert ohne `runId` | ✅ ERLEDIGT |
| BUG-4 | `MacroIntelligenceAgent` nicht injiziert in `decisions.py` | ✅ ERLEDIGT (Commit `0986c7b`) |
| BUG-5 | Webhook-Delivery — `send_webhook()` fehlte in `notification_adapter.py` | ✅ ERLEDIGT |
| BUG-6 | `LLMRateLimiterMiddleware` doppelt gemountet (Duplikat) | ✅ ERLEDIGT (PR #163) |

---

## §8 · KONVENTIONEN FÜR NEUE FEATURES

- Jedes neue Backend-Feature braucht: Service + Repository-Interface + Unit-Test
- Jedes neue Frontend-Feature braucht: Component + API-Client-Funktion
- SHAP-Werte immer als `List[ModelScore]` (nicht rohe Dict)
- LLM-Calls immer über `LLMClientInterface` (kein direkter anthropic-Import in Services)
- Kosten-Tracking: Jeder LLM-Call muss `cost_tracker.record()` aufrufen

---

## §9 · OFFENE AUFGABEN

### P0 — Kritisch (Demo-Blocker)

| ID | Aufgabe | Status |
|----|---------|--------|
| T1 | Conversational Discovery wiring (`start-client.tsx`) | ✅ ERLEDIGT |
| T2 | Memo ohne `model_run_id` ermöglichen | ✅ ERLEDIGT |
| T3 | Signal-Breakdown in Decision-Seite | ✅ ERLEDIGT (PR #164) |
| T4 | SHAP-Visualisierung direkt in Decision-Seite (nicht nur Factsheet) | 🔴 OFFEN |

### P1 — Wichtig (Projektanforderungen)

| ID | Aufgabe | Status |
|----|---------|--------|
| T5 | Rebalancing Eligibility-Fix | ✅ ERLEDIGT |
| T6 | Homepage Dashboard statt Marketing-Seite | ✅ ERLEDIGT |
| T7 | Preischart Backend — Stub-Status | ⚠️ UNKLAR (Frontend `PriceChart.tsx` vorhanden) |
| T8 | Monte Carlo Textinterpretation ("Mit X% Wahrscheinlichkeit...") | 🟠 IN ARBEIT |
| T9 | Unit Tests für 3 Application-Services | ✅ ERLEDIGT |
| T10 | E2E Tests — alle 13 spec-Dateien aktuell | ✅ ERLEDIGT |

### P2 — Qualität (TDD / Polishing)

| ID | Aufgabe | Status |
|----|---------|--------|
| T11 | Webhook-Delivery implementiert | ✅ ERLEDIGT |
| T12 | Chat Tool-Hints | ✅ ERLEDIGT (PR #162) |
| T13 | RAG Quellenangaben (Research, News, Steuer mit ExternalLink) | ✅ ERLEDIGT |
| T14 | Middleware-Duplikat entfernt | ✅ ERLEDIGT (PR #163) |
| T15 | Steuer Output — CSS-Grid mit Quellen-Sektion | ✅ ERLEDIGT |
| T16 | Eligibility Reason anzeigen | ✅ ERLEDIGT (PR #163) |

### P3 — Nice-to-have

| ID | Aufgabe | Status |
|----|---------|--------|
| T17 | Multi-Backtest-Vergleich (Quant / +ML / +Makro) | 🟡 IN ARBEIT |
| T18 | Sensitivitätsanalyse Signal-Gewichtung | 🟢 NOCH NICHT BEGONNEN |
| T19 | Budget-Anzeige im Chat | 🟡 IN ARBEIT |
| T20 | Profil-Badge in Navigation | 🟡 IN ARBEIT |
| T21 | Allocation-Methoden-Vergleich | 🟢 NOCH NICHT BEGONNEN |

---

## §10 · CLEANUP / DOCS

| Aufgabe | Status |
|---------|--------|
| README aktualisiert | ✅ ERLEDIGT (PR #159) |
| CONTRIBUTING aktualisiert | ✅ ERLEDIGT (PR #160) |
| Docs bereinigt | ✅ ERLEDIGT (PR #161) |

---

## §11 · TECHNISCHE SCHULDEN

| Datei | Problem | Priorität |
|-------|---------|-----------|
| `narrative_service.py:402` | Race-Condition bei Job-Status (TOCTOU) | Mittel |
| `news_ingestion_service.py:99` | Embedding-Index-Mismatch (stille Fehler) | Klein |
| `monte_carlo_service.py:124` | `dt=21` undokumentiert | Klein |
| `research-client.tsx:265` | Loose Type-Cast bei CSV-Export | Klein |
| `portfolio.py:42` | `YFinanceSwissAdapter` kein Cache | Klein |
| `macro.py:100` | `exc_info=True` logt falsche Exception | Klein |

---

## §12 · LETZTE WICHTIGE PRs / COMMITS

| Ref | Was |
|-----|-----|
| PR #159 | README cleanup |
| PR #160 | CONTRIBUTING cleanup |
| PR #161 | Docs cleanup |
| PR #162 | Chat Tool-Hints (T12) |
| PR #163 | Middleware-Duplikat entfernt (T14), Eligibility Reason (T16), BUG-6 fix |
| PR #164 | Signal-Breakdown in Decision-Seite (T3) |
| Commit `0bdeb48` | Unit-Tests für 3 Services, Memo-Fix, Discovery-Wiring |
| Commit `e5f683e` | E2E-Tests aktualisiert |
| Commit `0986c7b` | 10 Bug-Fixes Session 1 |
| Commit `5527309` | 8 Bug-Fixes Session 2 |
