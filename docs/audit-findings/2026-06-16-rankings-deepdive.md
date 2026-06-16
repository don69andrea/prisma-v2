# Audit-Findings — Rankings & Stock-Deep-Dive (2026-06-16)

## Getestete Funktionen
- POST /api/v1/runs (SMI-20, Tech-Big-12): OK
- GET /api/v1/runs/{id}/rankings: BUG (quality_classic systematisch null für SMI-20)
- GET /api/v1/runs/{id}/export (CSV): OK (Code-Review, Router korrekt implementiert)
- Frontend E2E-Test "CSV-Export" (frontend/e2e/rankings.spec.ts): BUG (Testsetup defekt)
- POST /api/v1/memos/generate (NESN, AAPL): OK, aber PERF-ISSUE (13-16s synchron)
- GET /api/v1/memos/jobs/{job_id} (Batch-Polling): UX-ISSUE (im Frontend nicht angebunden)
- GET /api/v1/stocks/XXXXX (ungültiger Ticker): OK (404)
- GET /api/v1/memos/{stock_id}/{fake_run_id}: OK (404)
- POST /api/v1/memos/generate mit fake model_run_id: OK (404, kein LLM-Call ausgelöst)
- GET /api/v1/decisions/live ohne Run (tickers-Query): OK (200/422 korrekt), Beobachtung zu Stub-Daten
- /research Pro-Mode "Agent-Aktivität": UX-ISSUE (vortäuschtes Fake-Progress-Theater)
- /watchlist Empty-State: OK

## Befunde

### F-RANK-1 — Quality-Classic-Modell liefert für gesamtes SMI-20-Universum keine Ränge
- **Bereich:** Funktional
- **Schweregrad:** Kritisch
- **Ort:** backend/infrastructure/providers/stub_fundamentals.py:10-141; backend/interfaces/rest/dependencies.py:93-101
- **Beschreibung:** `StubFundamentalsProvider._DEMO_DATA` enthält hardcodierte Fundamentaldaten ausschliesslich für US-Tech-Ticker (AAPL, MSFT, GOOGL, NVDA, JPM, AMZN, TSLA, META, NFLX, AMD, INTC, ORCL, CRM). Keiner der 20 SMI-Ticker ist enthalten, daher liefert `get_fundamentals()` für alle SMI-Werte `_EMPTY` (alle Felder None). Das QualityClassicModel selbst arbeitet korrekt (vergibt `rank=None` bei fehlenden Daten), aber das Resultat ist: in jedem SMI-20-Run ist `per_model_ranks.quality_classic` für alle 20 Titel `null`. Eine ganze Ranking-Dimension ist für das Schweizer Hauptuniversum faktisch funktionslos — bei einer "Schweizer Aktien-Analyse-Plattform" ein Kernfeature-Ausfall.
- **Reproduktion:** `POST /api/v1/runs {"universe_id":"<SMI-20-UUID>"}`, danach `GET /api/v1/runs/{id}/rankings` — alle 20 Einträge haben `per_model_ranks.quality_classic: null`.
- **Vorschlag:** Demo-Fundamentaldaten für mindestens die SMI-20-Ticker ergänzen, oder im Frontend/Memo-Layer deutlich kennzeichnen ("Quality-Daten für CH-Werte nicht verfügbar — Demo-Modus"), damit Nutzer nicht denken, das Modell sei kaputt. Langfristig: echten FundamentalsProvider anbinden (bereits als Issue #41 im Code vermerkt).

### F-RANK-2 — E2E-Test "CSV-Export" schlägt fehl, weil Fixture keinen API-Key sendet
- **Bereich:** Funktional (Testinfrastruktur)
- **Schweregrad:** Wichtig
- **Ort:** frontend/e2e/fixtures.ts:10-24 (`createTestUniverse`); backend/interfaces/rest/app.py:141 (`universes.router` mit `dependencies=_auth`)
- **Beschreibung:** `createTestUniverse()` ruft `POST /api/v1/universes` ohne `X-API-Key`-Header auf. Der Router ist global per `app.include_router(universes.router, dependencies=_auth)` mit `require_admin_api_key` geschützt. Gegen jede Instanz mit gesetztem `API_KEY` (wie die hier laufende, geseedete Test-Instanz) schlägt der Setup-Schritt mit 401 fehl, bevor der eigentliche CSV-Export-Testfall (`rankings.spec.ts:44`) überhaupt geprüft werden kann.
- **Reproduktion:** `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3090 PLAYWRIGHT_API_URL=http://localhost:8090 PLAYWRIGHT_NO_WEBSERVER=1 npx playwright test -g "CSV-Export"` → `Error: Universe-Setup fehlgeschlagen: 401 {"detail":"Invalid API key"}`.
- **Vorschlag:** `fixtures.ts` um einen `X-API-Key`-Header erweitern (aus `process.env.PLAYWRIGHT_API_KEY` o.ä.), damit der Test auch gegen API-Key-geschützte Umgebungen lauffähig ist. Aktuell ist der CSV-Export-Pfad damit in dieser Umgebung gar nicht automatisiert verifizierbar.

### F-RANK-3 — Memo-Batch-Job-Endpoint ohne jegliche Frontend-Anbindung
- **Bereich:** UX
- **Schweregrad:** Wichtig
- **Ort:** backend/interfaces/rest/routers/memos.py:108-220 (`POST /batch`, `GET /jobs/{job_id}`); frontend/lib/hooks/useStockMemo.ts
- **Beschreibung:** Es existiert kein Frontend-Code (`grep` über gesamtes `frontend/` nach `memos/batch`, `memos/jobs`, `BatchJob` liefert keine Treffer), der den Batch-Job-Endpoint nutzt. Nutzer können Memos nur einzeln über `MemoPanel`/`useStockMemo` generieren (1 synchroner Call pro Stock, 13-16s Wartezeit gemessen). Bei Rankings mit 12-20 Titeln gibt es keine Möglichkeit, "Memos für alle Top-10" in einem Batch anzufordern, obwohl das Backend dafür ausgelegt ist. Entweder ist das ein totes Backend-Feature oder eine unvollständige Frontend-Integration.
- **Reproduktion:** Code-Suche `grep -rn "memos/batch\|memos/jobs" frontend/` → keine Treffer.
- **Vorschlag:** Klären ob Batch-Generierung ein geplantes Feature ist; falls ja, UI-Trigger (z.B. "Alle Memos generieren" auf der Rankings-Tabelle) mit Polling auf `/jobs/{job_id}` ergänzen. Falls nicht: Endpoint als deprecated markieren oder entfernen, um Code-Drift zu vermeiden.

### F-RANK-4 — Memo-Generierung dauert 13-16s synchron ohne Fortschrittsanzeige im Detail
- **Bereich:** Performance / UX
- **Schweregrad:** Nice-to-have
- **Ort:** backend/interfaces/rest/routers/memos.py:86-105 (`POST /generate`); frontend/components/factsheet/MemoPanel.tsx:36-43
- **Beschreibung:** Einzelne Memo-Generierung (Claude-Aufruf) dauerte in beiden Testläufen 13.1s (NESN) bzw. 16.1s (AAPL) — als synchroner HTTP-Request. Das Frontend zeigt während dieser Zeit einen generischen Skeleton-Loader ("4 graue Balken"), aber keine Angabe, dass dies bis zu 15+ Sekunden dauern kann oder dass eine LLM-Anfrage läuft. Bei Verbindungsproblemen/Timeout (Backend behandelt `anthropic.APITimeoutError` → 504) bekommt der Nutzer nur "Memo konnte nicht geladen werden: ...".
- **Reproduktion:** `POST /api/v1/memos/generate` mit gültigem stock_id+model_run_id, Zeit messen.
- **Vorschlag:** Erwartungsmanagement im UI ("Analyse wird erstellt — dauert ca. 15s") statt generischem Skeleton, ggf. perspektivisch auf den ohnehin vorhandenen Batch-Job-/Polling-Mechanismus (F-RANK-3) umstellen, um synchrone Long-Requests zu vermeiden.

### F-RANK-5 — Research Pro-Mode täuscht Live-Multi-Agent-Aktivität und Makrodaten vor
- **Bereich:** UX
- **Schweregrad:** Wichtig
- **Ort:** frontend/app/research/research-client.tsx:32-181 (`AGENT_STEPS`, `useAgentLog`), :43-47 (`MOCK_MACRO`), :38-41 (`MOCK_SOURCES`)
- **Beschreibung:** Der Pro-Mode-Researchbereich zeigt ein "Agent-Aktivität"-Panel mit `MacroAgent`/`FilingRAG`/`QuantAgent`, das über feste `setTimeout`-Delays (0ms/500ms/1300ms) abläuft — unabhängig vom tatsächlichen Antwortverhalten der echten RAG-Calls (`retrieveSwissFilings`/`retrieveSecFilings`). Zusätzlich werden bei fehlenden echten Quellen `MOCK_SOURCES` ("Novartis GB 2025", "SNB Q1 2026") sowie statische `MOCK_MACRO`-Werte (SNB-Rate 1.0%, CHF/EUR 0.938) angezeigt, optisch nicht von echten Daten unterscheidbar. Das vermittelt dem Nutzer den Eindruck einer Live-Analyse mit echten Marktdaten, obwohl es sich teils um Platzhalter/Theater handelt.
- **Reproduktion:** Code-Review research-client.tsx; UI: `/research` im Pro-Mode aufrufen, beliebige Suche absenden, Quellen-Panel zeigt MOCK_SOURCES wenn `allSources.length === 0`.
- **Vorschlag:** Mock-Werte deutlich als "Beispiel/Platzhalter" kennzeichnen oder ausblenden statt sie wie Live-Daten zu rendern; Agent-Log an echte Promise-Resolution der RAG-Calls koppeln statt an feste Timer.

### F-RANK-6 — decisions/live liefert für mehrere Ticker identische Score-Werte (Stub-Verdacht)
- **Bereich:** Funktional
- **Schweregrad:** Nice-to-have
- **Ort:** GET /api/v1/decisions/live
- **Beschreibung:** Bei Abfrage mehrerer Ticker liefern NESN/ROG sowie AAPL/NVDA exakt identische `quant_score`/`ml_score`/`macro_score`/`weighted_score`-Werte. Funktional kein Fehler (Endpoint antwortet korrekt auch ohne vorherigen Run), aber starker Hinweis auf untergeordnete Stub/Demo-Implementierungen im ML- oder Macro-Score-Layer, analog zu F-RANK-1.
- **Reproduktion:** `GET /api/v1/decisions/live?tickers=NESN,ROG,UBSG,AAPL,NVDA` — NESN und ROG sowie AAPL und NVDA haben identische Scores.
- **Vorschlag:** Im Rahmen eines separaten ML/Macro-Audits prüfen, ob hier ebenfalls Stub-Daten in der aktuellen Umgebung aktiv sind, und ggf. wie bei F-RANK-1 kennzeichnen.

## Positive Befunde (kein Fix nötig)
- Edge Cases liefern durchgängig korrekte Statuscodes statt 500: `/stocks/XXXXX` → 404, `/memos/{stock_id}/{fake_run_id}` → 404, `/memos/generate` mit erfundener `model_run_id` → 404 (kein unnötiger LLM-Call).
- `MemoErrorCard`-Komponente (frontend/components/factsheet/MemoErrorCard.tsx) ist gut umgesetzt: klare Fehlermeldung, Retry-Button mit Spinner-State.
- Beide generierten Memos (NESN, AAPL) waren inhaltlich konsistent und erkannten selbständig die fehlende `quality_classic`-Dimension als Risiko/Kontext — gute Robustheit der Narrative-Engine gegenüber unvollständigen Eingabedaten.
- Watchlist-Empty-State (frontend/app/watchlist/watchlist-client.tsx) ist klar und handlungsleitend gestaltet.
