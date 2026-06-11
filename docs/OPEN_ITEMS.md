# OPEN ITEMS — PRISMA V2

> Lebendiges Planungsdokument. Wird nach jeder Arbeitssession aktualisiert.
> Zuletzt aktualisiert: 2026-06-12 (Claude Code Session — Sprint 1+2 abgeschlossen)

---

## Legende

| Symbol | Bedeutung |
|--------|-----------|
| 🔴 | Kritisch — blockiert Demo oder Kernfunktion |
| 🟠 | Wichtig — offizielle Projektanforderung unvollständig |
| 🟡 | Sollte erledigt werden — Qualität / TDD-Pflicht |
| 🟢 | Nice-to-have — Polishing / kleinere Verbesserungen |
| ✅ | Erledigt |

---

## 1 · FEATURE-LÜCKEN

### ✅ R2.4-1 — Conversational Discovery Engine verdrahtet

**Status:** DONE (Commit `0bdeb48`)  
**Offizielle Anforderung:** `/start` Conversational Discovery Engine — 5 Turns mit Haiku-Klassifikation

**Problem:**  
`frontend/app/start/start-client.tsx` ruft ausschliesslich die Legacy-Endpoints auf:
```
saveProfile(...)            →  POST /api/v1/profile
getPersonalizedStocks(...)  →  GET  /api/v1/discover
```

Die konversationellen Endpoints existieren im Backend (`discovery.py`) und sind vollständig implementiert, werden aber nie aufgerufen:
```
POST /api/v1/discovery/session   ← Session initialisieren
POST /api/v1/discovery/answer    ← Turn 1–4 je einzeln
POST /api/v1/discovery/complete  ← Profil abschliessen + Stocks holen
```

Die API-Client-Funktionen (`createDiscoverySession`, `submitAnswer`, `completeDiscovery`) existieren bereits in `frontend/lib/api/discovery.ts` — sie werden nur nie importiert und aufgerufen.

**Konsequenz der aktuellen Implementierung:**
- Turn 1: Haiku-Klassifikation (Beruf-Freitext → `financial_knowledge: low/medium/high`) läuft **nie**
- Konfidenz-Score pro Turn wird **nie** berechnet
- Session-State im Backend wird **nie** aufgebaut
- Das Profil wird einmalig am Ende in einem Bulk-POST gesendet statt schrittweise aufgebaut

**Was zu tun ist:**  
`start-client.tsx` auf Turn-by-Turn Ablauf umstellen:

1. Bei Step `beruf` → `createDiscoverySession()` → `sessionId` speichern
2. Nach `beruf`-Input → `submitAnswer(sessionId, 1, berufText)`
3. Nach `ziel`-Wahl → `submitAnswer(sessionId, 2, ziel)`
4. Nach `risiko`-Wahl → `submitAnswer(sessionId, 3, risiko)`
5. Nach `brands`-Wahl → `submitAnswer(sessionId, 4, selectedBrands)`
6. Am Ende → `completeDiscovery(sessionId)` → liefert `recommended_stocks`

**Relevante Dateien:**
- `frontend/app/start/start-client.tsx` — Hauptdatei, komplett umschreiben
- `frontend/lib/api/discovery.ts` — API-Funktionen sind ready, nur importieren
- `backend/interfaces/rest/routers/discovery.py` — Backend ready
- `backend/application/services/profile_classifier.py` — Haiku-Klassifikation ready
- `backend/application/services/discovery_service.py` — DiscoveryService ready

---

### ✅ Memo-Button für Discovery-User deaktiviert

**Status:** DONE (Commit `0bdeb48`)  
**Betroffen:** `frontend/app/stocks/[ticker]/page.tsx:237`

**Problem:**  
```tsx
<Button disabled={memoLoading || !runId}>
```
Wer über `/start` → `/discover` → `/stocks/[ticker]` kommt, hat kein `runId` in der URL. Der Button ist permanent deaktiviert. Der User kann keinen Memo generieren.

**Ursache im Backend:**  
`MemoGenerateRequest.model_run_id: UUID` ist Required. Ein leerer String `''` schlägt mit 422 fehl.

**Was zu tun ist:**

Backend (`backend/interfaces/rest/schemas/memos.py`):
```python
# Vorher:
class MemoGenerateRequest(BaseModel):
    stock_id: UUID
    model_run_id: UUID
    language: str = "de"

# Nachher:
class MemoGenerateRequest(BaseModel):
    stock_id: UUID
    model_run_id: UUID | None = None
    language: str = "de"
```

Backend (`backend/interfaces/rest/routers/memos.py`):  
Wenn `model_run_id` None: neuesten abgeschlossenen `RankingRun` für den Ticker suchen via `ranking_run_repo.get_latest_by_status("completed")`. Falls keiner vorhanden: Memo ohne Run-Kontext generieren (Narrative-Engine unterstützt das bereits).

Frontend (`frontend/app/stocks/[ticker]/page.tsx`):
```tsx
// Vorher:
disabled={memoLoading || !runId}

// Nachher:
disabled={memoLoading}
```

**Relevante Dateien:**
- `backend/interfaces/rest/schemas/memos.py`
- `backend/interfaces/rest/routers/memos.py`
- `backend/application/services/narrative_service.py`
- `frontend/app/stocks/[ticker]/page.tsx:237`

---

## 2 · TEST-COVERAGE-LÜCKEN

### 🟡 Unit-Tests für 3 Application-Services fehlen

**TDD-Pflicht gemäss AGENTS.md:** Für alle Application-Services müssen Unit-Tests vor oder zusammen mit der Implementierung existieren.

#### ✅ 2.1 `factsheet_service.py` — Unit-Tests vorhanden (10 Tests, Commit `0bdeb48`)

**Datei:** `backend/application/services/factsheet_service.py`  
**Was zu testen ist:**
- `get_factsheet(ticker)` mit vorhandenen Daten → korrekte Aggregation
- `get_factsheet(ticker)` wenn Stock nicht gefunden → None zurück
- `get_factsheet(ticker)` wenn RankingRun ohne Ergebnis für ticker → `latest_ranking=None`
- SHAP-Werte korrekt in `ModelScore`-Objekte konvertiert
- `model_scores` korrekt sortiert nach Score (absteigend)

**Test-Datei zu erstellen:** `backend/tests/unit/application/test_factsheet_service.py`

#### ✅ 2.2 `news_retrieval_service.py` — Unit-Tests vorhanden (15 Tests, Commit `0bdeb48`)

**Datei:** `backend/application/services/news_retrieval_service.py`  
**Was zu testen ist:**
- `retrieve(query, k)` → korrekte Weiterleitung an Repository
- `retrieve(query, k, ticker=...)` → Ticker-Filter wird übergeben
- Leeres Repository → leere Liste
- Embedding-Fehler wird korrekt propagiert

**Test-Datei zu erstellen:** `backend/tests/unit/application/test_news_retrieval_service.py`

#### ✅ 2.3 `ranking_run_service.py` — Unit-Tests vorhanden (18 Tests, Commit `0bdeb48`)

**Datei:** `backend/application/services/ranking_run_service.py`  
**Was zu testen ist:**
- `create_run(universe_id, weight_config)` → korrekter Status initial `pending`
- `start_run(run_id)` → Status-Übergang `pending → running`
- `complete_run(run_id, results)` → Status `completed`, Ergebnisse persistiert
- `fail_run(run_id, error)` → Status `failed`
- `get_run(run_id)` wenn nicht gefunden → None
- `list_runs()` → korrekte Paginierung

**Test-Datei zu erstellen:** `backend/tests/unit/application/test_ranking_run_service.py`

---

### 🟡 E2E-Tests — Aktualität prüfen

**Pfad:** `frontend/e2e/` (12 Test-Dateien)

Mehrere E2E-Tests referenzieren möglicherweise Routes oder Elemente die sich durch die Navigation-Restrukturierung (R2.4-4) verändert haben. Insbesondere:
- Tests die `/rankings` als Startpunkt nutzen (Back-Button geht jetzt zu `/discover`)
- Tests die den Memo-Button testen (war immer disabled ohne runId)

**Empfehlung:** Alle 12 E2E-Dateien kurz durchsehen und veraltete Selektoren/Routes aktualisieren.

---

## 3 · BEREITS GEFIXTE BUGS (Referenz)

In dieser Session wurden folgende Bugs behoben (alle in `develop` committed):

### Commit `0986c7b` — 10 Bugs (Session 1)
| # | Problem | Fix |
|---|---------|-----|
| 1 | `chat.py` + `reports.py` nie in `app.py` gemountet | Router-Imports + `include_router` hinzugefügt |
| 2 | `MacroIntelligenceAgent` nicht injiziert in `decisions.py` | `get_llm_client` DI + Agent-Konstruktor |
| 3 | `get_signals()` serialisiert (Timeouts) | `asyncio.gather()` parallelisiert |
| 4 | `get_personalized_universe()` serialisiert | `asyncio.gather()` + `_score_stock()` Helper |
| 5 | SNB-Fallback fehlte Juni-2025-Eintrag (0%) | `(date(2025, 6, 19), 0.0)` hinzugefügt |
| 6 | Rebalancing zeigt immer `is_3a_eligible=False` | `stock_repo` via FastAPI DI injiziert |
| 7 | Homepage zeigte statische Marketing-Seite | Ersetzt durch `DashboardClient` |
| 8 | `/discover` nicht in Nav | Route + Nav-Eintrag hinzugefügt |
| 9 | `LISP` (PS) statt `LISN` (Namenaktie) | Ticker korrigiert |
| 10 | R2.4-1 Status falsch als `DONE` | Korrigiert zu `⚠️ PARTIAL` |

### Commit `5527309` — 8 Bugs (Session 2, aus 6-Agenten-Analyse)
| # | Problem | Fix |
|---|---------|-----|
| 1 | `ranking_run_repository.save_results()` kein `commit()` | `await self._session.commit()` hinzugefügt |
| 2 | `rebalancing_service._resolve_eligibility()` Logik invertiert | `not is_3a_account` → `False` |
| 3 | `report_service.py` falscher Constructor-Parameter | `swiss_stock_repo=` → `stock_repo=` |
| 4 | `swiss_filing_retrieval_service` blocking I/O | `voyage.embed()` → `asyncio.to_thread()` |
| 5 | Portfolio-Agent Risk-Parity Floor zu tief | Volatility-Floor 0.01 → 0.05 |
| 6 | `profile_classifier` JSON ohne Error-Handling | try/except JSONDecodeError + Logging |
| 7 | `test_memo_batch_endpoint` sync Tests mit async Fixtures | `@pytest_asyncio.fixture async` → `@pytest.fixture` |
| 8 | `Dockerfile.frontend` non-reproducible | `package-lock.json` + `npm ci` |

### Commit `e063f28` — Cowork-Agent Befunde + Docs
| # | Problem | Fix |
|---|---------|-----|
| 1 | Back-Button → `/rankings` statt `/discover` | Href + Label korrigiert |
| 2 | Discovery-Fallback speichert `stocks: []` | Fallback aus Brand-Auswahl aufgebaut |
| 3 | Capstone-Referenzen in README/CLAUDE.md/AGENTS.md | Bereinigt → FHNW BI Module |

---

## 4 · TECHNISCHE SCHULDEN (MEDIUM-Priorität)

Diese Punkte blockieren nichts, sollten aber irgendwann behoben werden:

| Datei | Problem | Aufwand |
|-------|---------|---------|
| `narrative_service.py:402` | Race-Condition bei Job-Status (TOCTOU) | Mittel |
| `news_ingestion_service.py:99` | Embedding-Index-Mismatch kann stille Fehler erzeugen | Klein |
| `monte_carlo_service.py:124` | `dt=21` undokumentiert (Handelstage?) | Klein |
| `research-client.tsx:265` | Loose Type-Cast bei CSV-Export | Klein |
| `portfolio.py:42` | `YFinanceSwissAdapter` per-Request neu erstellt (kein Cache) | Klein |
| `macro.py:100` | `exc_info=True` logt falsche Exception | Klein |
| `render.yaml` | pgvector-Aktivierung nicht dokumentiert | Trivial |
| `llm-smoke.yml` | Kein API-Key-Validierungsschritt vor Test | Klein |

---

## 5 · BEKANNTE EINSCHRÄNKUNGEN (Designentscheidungen, nicht fixbar)

Diese Punkte sind bewusste Einschränkungen, die dokumentiert aber nicht "gefixt" werden sollten:

- **ISIN-Lücken:** ABBN, BALN (delisted), STMN haben `isin=NULL` im Seed. ISINs müssen manuell via SIX Exchange verifiziert werden. yfinance liefert für `.SW`-Ticker kein `isin`-Feld.
- **SNB Rate History:** Endet Juni 2025. Für spätere Daten würde die History-Tabelle echte SNB-Entscheide brauchen — keine Fake-Daten hinzufügen.
- **Memo ohne Run:** Aktuell nur mit `model_run_id` möglich (→ siehe Open Item 2 oben).
- **Cost-Tracker Race-Condition:** Soft-Limit ohne DB-Lock. Zwei parallele Calls können beide `check_cap` passieren. Bewusst akzeptiert für Capstone-Volumen.

---

## 6 · PRIORISIERUNGSEMPFEHLUNG

```
Sprint 1 (Feature-Completeness):
├── R2.4-1: Discovery Conversational Wiring  [~4-6h]
└── Memo ohne model_run_id                  [~2-3h]

Sprint 2 (Test-Qualität):
├── test_factsheet_service.py               [~2h]
├── test_news_retrieval_service.py          [~1h]
└── test_ranking_run_service.py             [~2h]

Sprint 3 (Polishing):
├── E2E-Tests aktualisieren                 [~2h]
└── Technische Schulden (Auswahl)           [nach Bedarf]
```

**Nicht priorisiert (bewusst weggelassen):**
- Neue Features über die Projektanforderungen hinaus
- Vollständige Test-Coverage für alle 50+ Domain-Klassen
- Refactoring der CORS/Config-Validierung für Production

---

## 7 · VERWEISE

| Dokument | Zweck |
|----------|-------|
| `CLAUDE.md` | Projektstatus-Tabelle (DONE/PARTIAL/NEXT) |
| `AGENTS.md` | Coding-Konventionen, Branch-Workflow |
| `backend/interfaces/rest/routers/discovery.py` | Backend-Endpunkte für R2.4-1 |
| `frontend/lib/api/discovery.ts` | Frontend-API-Client für R2.4-1 (fertig, nur nicht aufgerufen) |
| `frontend/app/start/start-client.tsx` | Hauptdatei die für R2.4-1 umgeschrieben werden muss |
| `backend/interfaces/rest/schemas/memos.py` | Schema-Änderung für Memo ohne runId |
