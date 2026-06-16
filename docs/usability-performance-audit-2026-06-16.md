# Usability-, Funktions- & Performance-Audit — 2026-06-16

Branch: `worktree-usability-performance-audit-2026-06-16`
Erstellt durch: Paralleler 7-Agenten-Audit (Discovery/Onboarding, Rankings/Deep-Dive,
Portfolio/Macro/Fonds/Steuer, Backtest/Crypto/Universes, News/Alerts/Chat/Reports,
Performance/Last, Render-Smoke-Test) gegen einen isolierten lokalen Stack mit echten API-Keys.
Vollständige Einzelbefunde inkl. Reproduktionsschritten: `docs/audit-findings/2026-06-16-*.md`.
Status: 🔄 IN PROGRESS

---

## Übersicht

| Bereich | Kritisch | Wichtig | Nice-to-have |
|---|---|---|---|
| Discovery & Onboarding | 0 | 3 | 3 |
| Rankings & Stock-Deep-Dive | 1 | 3 | 2 |
| Portfolio/Macro/Fonds/Steuer | 2 | 4 | 2 |
| Backtest/Crypto/Universes | 1 | 4 | 3 |
| News/Alerts/Chat/Reports | 0 | 3 | 6 |
| Performance | 1 | 0 | 1 |
| Render Smoke-Test | 0 | 2 | 2 |
| **Total** | **5** | **19** | **19** |

Zusätzlich verifiziert (kein Fund, positiv bestätigt): SSRF-Schutz auf Webhook-Alerts hält
gegen mehrere Payload-Varianten; Decision-Audit-Trail ist inhaltlich nachvollziehbar; alle
Edge-Case-HTTP-Codes (404 statt 500) funktionieren in Discovery/Rankings korrekt; bekannter
Backtest-Series-Typ-Bug (string[] vs number[]) bleibt gefixt; keine neuen ungeschützten
blockierenden Event-Loop-Calls seit dem letzten Audit.

**Umgebungs-Caveat:** Der Audit-Stack hatte anfangs kein `frontend/.env.local` mit
`NEXT_PUBLIC_API_KEY` — dadurch lieferten rein client-seitige Browser-Calls (v.a. in Block
Backtest/Crypto/Universes) 401-Fehler, die nichts mit der Produktanwendung zu tun haben
(F-BTCR-8). Wurde während des Audits nachträglich behoben (`.env.local` ergänzt). Alle unten
gelisteten Funde wurden zusätzlich gegen die Backend-API direkt verifiziert und sind unabhängig
von diesem Setup-Detail real.

---

## KRITISCHE FIXES (alle vor weiterem Merge-Risiko zu beheben)

### K-1 — Quality-Classic-Modell liefert für gesamtes SMI-20-Universum `null`
- **Datei:** `backend/infrastructure/providers/stub_fundamentals.py:10-141`
- **Problem:** `StubFundamentalsProvider._DEMO_DATA` enthält nur US-Tech-Ticker. Keiner der 20
  SMI-Ticker ist enthalten → `quality_classic`-Rang ist für das gesamte Schweizer
  Hauptuniversum `null`. Bei einer "Schweizer Aktien-Plattform" ein Kernfeature-Ausfall.
- **Fix:** Demo-Fundamentaldaten für mindestens die SMI-20-Ticker ergänzen, oder UI/Memo-Layer
  deutlich kennzeichnen ("Quality-Daten für CH-Werte nicht verfügbar — Demo-Modus").
- **Quelle:** `docs/audit-findings/2026-06-16-rankings-deepdive.md` (F-RANK-1)
- **Status:** ✅ Erledigt — [PR #201](https://github.com/don69andrea/prisma-v2/pull/201)

### K-2 — Monte-Carlo liefert falsche Kursdaten für Schweizer Ticker und crasht
- **Datei:** `backend/application/services/monte_carlo_service.py:150-169` (`_fetch_ticker_params`)
- **Problem:** Ruft `yf.download(ticker, ...)` mit dem rohen PRISMA-Ticker statt dem
  `YFinanceSwissAdapter`-Suffix-Mapping auf. "ROG" matched auf Rogers Corporation (US) statt
  Roche; "CFR" auf Cullen/Frost Bankers (US) statt Richemont. Resultat: NaN in den Kursdaten →
  `ValueError: cannot convert float NaN to integer` (HTTP 422).
- **Fix:** `_fetch_ticker_params` muss das Ticker-Suffix-Mapping aus `YFinanceSwissAdapter`
  nutzen; zusätzlich NaN-Validierung mit klarer 422-Meldung statt generischem Exception-Text.
- **Quelle:** `docs/audit-findings/2026-06-16-portfolio-macro-fonds-steuer.md` (F-PORT-1)
- **Status:** ✅ Erledigt — [PR #202](https://github.com/don69andrea/prisma-v2/pull/202)

### K-3 — Steuer-Einschätzung liefert identischen, fachlich falschen Output für US-Aktien
- **Datei:** `backend/application/agents/steuer_agent.py` (Fallback-Pfad)
- **Problem:** `/steuer/einschaetzung` läuft im `model_version: "fallback"`-Modus (LLM-Pfad
  greift nicht) und gibt für TSLA denselben Text wie für NESN aus ("Verrechnungssteuer 35%,
  Formular 103") — fachlich falsch für US-Aktien (US-Quellensteuer, DA-1/W8BEN gelten dort).
- **Fix:** Fallback-Pfad muss CH- vs. Nicht-CH-Aktien unterscheiden (3a-Eligibility-Lookup oder
  Länder-Flag) und unterschiedliche Steuerarten-Templates ausgeben. Root Cause klären, warum
  der LLM-Pfad nicht greift.
- **Quelle:** `docs/audit-findings/2026-06-16-portfolio-macro-fonds-steuer.md` (F-STEUER-1)
- **Status:** ✅ Erledigt — [PR #203](https://github.com/don69andrea/prisma-v2/pull/203)

### K-4 — Universe mit existierendem Namen anlegen liefert rohe HTTP 500
- **Datei:** `backend/infrastructure/persistence/repositories/universe_repository.py:26-44`,
  `backend/application/services/universe_service.py:51-64`
- **Problem:** UNIQUE-Index auf `universes.name`, aber `save()` nutzt `ON CONFLICT (id)` —
  Namens-Konflikte werden nie abgefangen. `IntegrityError` propagiert ungefangen bis zum
  globalen Handler → `{"detail":"Interner Serverfehler."}` (500) im Frontend sichtbar.
- **Fix:** `IntegrityError`/`UniqueViolationError` im Service/Repository abfangen, als
  `DuplicateUniverseName`-Exception werfen, im Router auf HTTP 409 mit Klartextmeldung mappen
  (Pattern existiert bereits in `news_repository.py`).
- **Quelle:** `docs/audit-findings/2026-06-16-backtest-crypto-universes.md` (F-BTCR-3)
- **Status:** ✅ Erledigt — [PR #204](https://github.com/don69andrea/prisma-v2/pull/204)

### K-5 — Rate-Limiter blockiert LLM-freie Stocks-Endpoints fälschlich
- **Datei:** `backend/interfaces/rest/rate_limiter.py:32` (`_LLM_PREFIXES`)
- **Problem:** Prefix `"/api/v1/stocks"` ist zu breit gefasst und erfasst auch die reinen
  GET-Endpoints (Liste, Factsheet) ohne LLM-Call. Limit von 10 Req/IP/60s killt jede normale
  Nutzung der Stocks-Liste nach wenigen Klicks — bereits ab 5 gleichzeitigen Usern >60%
  Error-Rate (429), unabhängig von echter Serverlast (DB-Latenz bleibt durchgehend <40ms p95).
- **Fix:** `_LLM_PREFIXES` auf tatsächlich LLM/Embedding-auslösende Pfade einschränken
  (`/discovery`, `/chat`, `/memos/generate`, `/memos/batch`, `/macro/score`,
  `/portfolio/monte-carlo`, `/steuer`, `/decisions/explain`, `/news/ingest`). Reine
  GET-Listen/Factsheet-Pfade ausnehmen oder mit separatem, grosszügigerem Limit versehen.
- **Quelle:** `docs/audit-findings/2026-06-16-performance.md` (F-PERF-1)
- **Status:** ✅ Erledigt — [PR #205](https://github.com/don69andrea/prisma-v2/pull/205)

---

## WICHTIGE FIXES

### W-1 — Browser-Reload mitten im Discovery-Flow verwirft gesamten Fortschritt
- **Datei:** `frontend/app/start/start-client.tsx`
- **Problem:** State lebt nur in `useState`, kein Storage/URL-Sync. Reload wirft Nutzer zurück
  zum Landing-Screen, beantwortete Turns bleiben als verwaiste Session in der DB.
- **Fix:** `sessionId` + aktueller Step in `sessionStorage`/Query-Param spiegeln.
- **Quelle:** `2026-06-16-discovery-onboarding.md` (F-DISC-1) — **Status:** ⬜ TODO

### W-2 — Race Condition: Discovery-Turns 1-4 vs. 5-7 ungesichert
- **Datei:** `frontend/app/start/start-client.tsx:1245-1261,1165-1242`
- **Problem:** `handleBrandsSubmit` feuert Turns 1-4 unawaited im Hintergrund. Schnelles
  Durchklicken kann dazu führen, dass Turns 5-7 mit einer nie registrierten Session-UUID laufen
  → falsches Profil (z.B. "Sektoren: —" trotz ausgewählter Marken).
- **Fix:** Promise aus `handleBrandsSubmit` zurückgeben/awaiten, bevor Turns 5-7 gesendet werden.
- **Quelle:** F-DISC-2 — **Status:** ⬜ TODO

### W-3 — `POST /discovery/complete` liefert HTTP 500 statt 4xx bei zweitem Aufruf ohne Turn 1
- **Datei:** `backend/domain/entities/investor_profile.py:60-73`,
  `backend/interfaces/rest/routers/discovery.py:261-284`
- **Problem:** Pydantic-Validator wirft `ValueError` bei `profession is None` +
  `onboarding_complete=True`, läuft aber erst bei Neukonstruktion aus der DB — landet als 500
  statt 400/422.
- **Fix:** Expliziter Check vor dem Setzen von `onboarding_complete=True`, sonst 422 mit
  klarer Meldung; Endpoint generell idempotent machen.
- **Quelle:** F-DISC-3 — **Status:** ⬜ TODO

### W-4 — E2E-Test "CSV-Export" gegen API-Key-geschützte Umgebungen kaputt
- **Datei:** `frontend/e2e/fixtures.ts:10-24`
- **Problem:** `createTestUniverse()` sendet keinen `X-API-Key`-Header, schlägt mit 401 fehl.
- **Fix:** Header aus `process.env.PLAYWRIGHT_API_KEY` ergänzen.
- **Quelle:** F-RANK-2 — **Status:** ⬜ TODO

### W-5 — Memo-Batch-Job-Endpoint ohne Frontend-Anbindung
- **Datei:** `backend/interfaces/rest/routers/memos.py:108-220`
- **Problem:** Kein Frontend-Code nutzt `/memos/batch`/`/memos/jobs` — totes Backend-Feature
  oder unvollständige Integration.
- **Fix:** Klären ob geplant; falls ja UI-Trigger + Polling ergänzen, sonst als deprecated
  markieren.
- **Quelle:** F-RANK-3 — **Status:** ⬜ TODO

### W-6 — Research Pro-Mode täuscht Live-Multi-Agent-Aktivität und Makrodaten vor
- **Datei:** `frontend/app/research/research-client.tsx:32-181`
- **Problem:** Festes `setTimeout`-Agent-Log unabhängig vom echten RAG-Call-Status;
  `MOCK_SOURCES`/`MOCK_MACRO` optisch nicht von echten Daten unterscheidbar.
- **Fix:** Mock-Werte deutlich kennzeichnen/ausblenden; Agent-Log an echte Promise-Resolution
  koppeln.
- **Quelle:** F-RANK-5 — **Status:** ⬜ TODO

### W-7 — Monte-Carlo: sequenzieller Ticker-Fetch als Performance-Hotspot
- **Datei:** `backend/application/services/monte_carlo_service.py:106-129`
- **Problem:** Ticker-Daten werden sequenziell statt parallel geholt — 13s bei 5 Holdings,
  skaliert linear mit Anzahl Holdings.
- **Fix:** `asyncio.gather` statt sequenzieller Loop; historische Kursdaten cachen (TTL).
- **Quelle:** F-PORT-2 — **Status:** ⬜ TODO

### W-8 — `/portfolio/allocate` vs. `/portfolio/rebalance` API-Design-Diskrepanz
- **Datei:** `backend/interfaces/rest/schemas/portfolio.py:11-18`
- **Problem:** `/allocate` erwartet nur `run_id` (Ranking-Kontext), kein direkter
  Ticker+Stückzahl-Input möglich — für Endnutzer mit eigenem Portfolio unklar, welcher
  Endpoint/Flow zu nutzen ist.
- **Fix:** Naming/Doku klären ("KI-Empfehlung" vs. "Mein Portfolio"); optional
  Stückzahl-Eingabe mit Live-Kurs-Lookup im Rebalance-Formular ergänzen.
- **Quelle:** F-PORT-3 — **Status:** ⬜ TODO

### W-9 — `/portfolio/rebalance` validiert Ticker nicht gegen bekanntes Universum
- **Datei:** `backend/interfaces/rest/routers/rebalancing.py:30-43`
- **Problem:** 53-Positionen-Request mit 20 erfundenen Tickern wird klaglos mit HTTP 200
  verarbeitet inkl. `is_3a_eligible: true`-Default.
- **Fix:** Ticker vor Verarbeitung gegen `SwissStockRepository` validieren, bei unbekannten
  Tickern 422 mit Liste zurückgeben.
- **Quelle:** F-PORT-4 — **Status:** ⬜ TODO

### W-10 — Makro-Score ist ticker-unabhängig (immer identischer Wert 80.0)
- **Datei:** `backend/interfaces/rest/routers/macro.py:70-78`
- **Problem:** `sector`-Parameter wird nie an `get_macro_score()` übergeben — Export-Sektor-Bonus
  greift nie, Score bleibt für jeden Ticker auf Baseline.
- **Fix:** Sektor-Info aus `SwissStockRepository` nachschlagen und übergeben.
- **Quelle:** F-MACRO-1 — **Status:** ⬜ TODO

### W-11 — Backtest ignoriert angeforderten Zeitraum stillschweigend (504-Tage-Fenster)
- **Datei:** `backend/application/services/backtest_service.py:87-98`,
  `frontend/app/backtest/page.tsx:501`
- **Problem:** `get_prices()` liefert immer nur die letzten 504 Handelstage, Service filtert
  erst nachträglich. Frontend zeigt weiterhin das ursprünglich eingegebene (falsche) Datumsfenster.
- **Fix:** API soll tatsächlich abgedecktes Fenster zurückgeben, Frontend zeigt dieses an;
  alternativ 422/Warning bei zu langem Zeitraum.
- **Quelle:** F-BTCR-1 — **Status:** ⬜ TODO

### W-12 — `CRYPTO_FEATURE_ENABLED` ist ein totes Feature-Flag
- **Datei:** `backend/config.py:60-61`, `backend/interfaces/rest/routers/crypto.py`
- **Problem:** Setting existiert, wird aber nirgends gelesen — Crypto-Modul bleibt aktiv,
  egal welcher Wert gesetzt ist.
- **Fix:** Flag im Router verdrahten (404/503 + Frontend-Fallback) oder als totes Feld entfernen.
- **Quelle:** F-BTCR-2 — **Status:** ⬜ TODO

### W-13 — Universe-Sync markiert valide SMI-Ticker durchgehend als "failed"
- **Datei:** `backend/application/services/universe_service.py:66-96`
- **Problem:** `sync` für SMI-20 liefert `synced_count: 0`, alle 20 realen Ticker als
  `failed_tickers` — Provider-Konfigurationsproblem, keine Unterscheidung "Provider down" vs.
  "Ticker ungültig".
- **Fix:** Root-Cause-Analyse Fundamentals-/MarketData-Provider-Konfiguration; Fehlerarten
  unterscheiden.
- **Quelle:** F-BTCR-5 — **Status:** ⬜ TODO

### W-14 — Crypto Pro-Tabelle rundet Niedrigpreis-Coins auf "CHF 0"
- **Datei:** `frontend/components/crypto/CryptoProRow.tsx:9-12,55`
- **Problem:** Feste 0 Dezimalstellen für alle Preise — ADA (~CHF 0.30-0.50) zeigt "CHF 0".
- **Fix:** Dynamische Dezimalstellen abhängig von Preisgrösse.
- **Quelle:** F-BTCR-6 — **Status:** ⬜ TODO

### W-15 — Chat-Tool `get_factsheet` schlägt mit `.SW`-Suffix fehl
- **Datei:** `backend/application/services/chat_service.py:97-99,202`
- **Problem:** Claude ruft tool-konform `get_factsheet("NESN.SW")` auf, Backend stripped das
  Suffix nicht → "Keine Daten gefunden", Chat endet ohne Antwort an den Nutzer.
- **Fix:** Suffix-Stripping analog zur REST-Stocks-Router-Normalisierung.
- **Quelle:** F-COMM-2 — **Status:** ⬜ TODO

### W-16 — Chat-Endpoint trackt keine LLM-Kosten im Admin-Cost-Dashboard
- **Datei:** `backend/application/services/chat_service.py`
- **Problem:** Kein `CostTracker`-Aufruf nach Claude-Calls — Budget-Cap-System hat blinden
  Fleck bei Chat.
- **Fix:** `CostTracker.track_call(...)` nach jedem Claude-Call im ChatService ergänzen.
- **Quelle:** F-COMM-3 — **Status:** ⬜ TODO

### W-17 — News-Retrieve: Ticker-Filter liefert durchgehend 0 Treffer
- **Datei:** `backend/application/services/news_ingestion_service.py` (`TickerNer.extract`)
- **Problem:** Nach Ingestion von 101 Artikeln hat jeder Treffer `tickers: []` — Ticker-Filter
  praktisch nutzlos.
- **Fix:** NER-Erkennung/Aliasliste für Schweizer Firmennamen kalibrieren.
- **Quelle:** F-COMM-5 — **Status:** ⬜ TODO

### W-18 — Render-Backend deployed veraltete Version (2.0.0 statt 2.2.0)
- **Ort:** Backend `/health` vs. `pyproject.toml`
- **Problem:** Production hat nicht den aktuellen `main`-Stand — bekanntes Problem (fehlende
  Deploy-Hook-Secrets laut PR #200).
- **Fix:** Deploy-Hook-Konfiguration auf Render-Dashboard prüfen/nachtragen (Repo-Owner-Aktion,
  kein Code-Fix).
- **Quelle:** F-RENDER-1 — **Status:** ⬜ TODO (Repo-Owner-Aktion, nicht per PR lösbar)

### W-19 — Render Cold-Start (~52s Backend, ~12s Frontend) ohne Nutzer-Hinweis
- **Ort:** Backend `/health`, Frontend `/`
- **Problem:** Free-Tier-Cold-Start fühlt sich für Endnutzer wie ein Hänger/Absturz an.
- **Fix:** Ladeindikator/Hinweistext im Frontend für langsame erste Antwort; optional externer
  Uptime-Monitor zum Warmhalten.
- **Quelle:** F-RENDER-2 — **Status:** ⬜ TODO

---

## NICE-TO-HAVE

| # | Kurzbeschreibung | Quelle | Status |
|---|---|---|---|
| I-1 | "Profil fertigstellen"-Button ohne sofortigen Disabled-State | F-DISC-4 | ⬜ |
| I-2 | Leere Freitext-Antwort wird ohne Validierung akzeptiert (`min_length`) | F-DISC-5 | ⬜ |
| I-3 | fadeIn-Animation macht Screens kurz kontrastarm/schwer lesbar | F-DISC-6 | ⬜ |
| I-4 | Memo-Generierung 13-16s ohne Erwartungsmanagement im UI | F-RANK-4 | ⬜ |
| I-5 | `decisions/live` liefert für mehrere Ticker identische Scores (Stub-Verdacht) | F-RANK-6 | ⬜ |
| I-6 | Quant-Score-Text hardcoded "/100" bei tatsächlicher 0-10-Skala | F-PORT-5 | ⬜ |
| I-7 | 3a-Eligibility für Nicht-CH-Ticker liefert 404 statt `eligible:false` | F-STEUER-2 | ⬜ |
| I-8 | Universe-Erstellung validiert Ticker-Existenz nicht (erst beim Sync sichtbar) | F-BTCR-4 | ⬜ |
| I-9 | Fear&Greed-Gauge zeigt bei Query-Error dauerhaft Skeleton statt Fehlermeldung | F-BTCR-7 | ⬜ |
| I-10 | Lokaler Dev-Stack ohne `NEXT_PUBLIC_API_KEY` (Setup-Gap, inzwischen behoben) | F-BTCR-8 | ✅ |
| I-11 | SSRF-Schutz: kein DNS-Resolve-Check gegen DNS-Rebinding (Tiefenverteidigung) | F-COMM-1 | ⬜ |
| I-12 | PDF-Report liefert 500 statt 503 bei fehlendem WeasyPrint (OSError unbehandelt) | F-COMM-4 | ⬜ |
| I-13 | News-Retrieve: niedrige Relevanz der Top-Treffer ohne Konfidenz-Hinweis | F-COMM-6 | ⬜ |
| I-14 | News-Ingest ohne Ad-hoc-Text/URL-Parameter, synchron ~33s | F-COMM-7 | ⬜ |
| I-15 | `/runs/{id}/export` liefert CSV, Naming verwechselbar mit PDF-Report | F-COMM-8 | ⬜ |
| I-16 | Decision-Audit-Records nur on-demand, nicht automatisch bei Run-Abschluss | F-COMM-9 | ⬜ |
| I-17 | 4 Frontend-Routen mit 60-75% überdurchschnittlichem First-Load-JS (Charts) | F-PERF-2 | ⬜ |
| I-18 | Kein OpenAPI-Schema in Production erreichbar (vermutlich gewollt) | F-RENDER-3 | ⬜ |
| I-19 | Prozent- vs. CHF-Formatierung nutzt zwei verschiedene Strategien (Wartungsrisiko) | F-PORT (UX-Abschnitt) | ⬜ |
| I-20 | `frontend/e2e/06-alerts.spec.ts` transient flaky in CI (Delete→Empty-State-Timing, 1x beobachtet, beim Retry grün) | PR #201 CI-Run | ⬜ |

---

## Nächste Schritte

1. K-1 bis K-5 sofort fixen (TDD, je eigener Branch/PR, unabhängige Dateien — sicher
   parallelisierbar).
2. W-1 bis W-19: Rückfrage an User vor Umsetzung, da hohes PR-Volumen (Team-Review-Kapazität
   für ein 3-Personen-Team berücksichtigen).
3. W-18 (Render-Deploy-Version) ist keine Code-Aufgabe — an Repo-Owner für Render-Dashboard
   weiterleiten.
