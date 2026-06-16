# Usability-, Funktions- & Performance-Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jede Funktion von PRISMA V2 live durchtesten (Funktionalität + UX), die App per Lasttest
an ihre Grenzen treiben, Befunde dokumentieren und priorisierte Fixes als PRs gegen `main`
liefern.

**Architecture:** Phasiertes Multi-Agent-Audit auf einem isolierten Worktree-Stack
(`/Users/andreapetretta/prisma-v2/.claude/worktrees/usability-performance-audit-2026-06-16`,
Branch `worktree-usability-performance-audit-2026-06-16`, gebrancht von aktuellem `origin/main`).
Phase A (Tasks 1-5, parallel): Funktional+UX je Feature-Block, ein gemeinsamer Stack
(DB :5433, Backend :8090, Frontend :3090). Phase B (Task 6): exklusiver Last-/Perf-Stack.
Phase C (Task 7): read-only Render-Smoke-Test. Phase D (Tasks 8-9): Konsolidierung + Fix-PRs.

**Tech Stack:** FastAPI/SQLAlchemy/Postgres+pgvector (Backend), Next.js/React (Frontend),
pytest/vitest/Playwright (Tests), Docker (DB-Isolation), Locust (Lasttest), `gh` CLI (PRs).

Vollständiger Kontext/Begründung: siehe
`docs/superpowers/specs/2026-06-16-usability-performance-audit-design.md`.

---

## Gemeinsame Spielregeln für alle Tasks

- Arbeitsverzeichnis ist immer der oben genannte Worktree-Pfad. Niemals in
  `/Users/andreapetretta/prisma-v2` oder `/Users/andreapetretta/Desktop/prisma-v2` schreiben
  (andere aktive Sessions).
- Stack für Phase A ist bereits oben (läuft): `curl http://localhost:8090/health` muss
  `{"status":"ok",...}` liefern, `curl http://localhost:3090` muss 307 → `/start` liefern.
  Falls nicht erreichbar: im Worktree `source .venv/bin/activate && set -a && source .env &&
  set +a && nohup uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port 8090 >
  /tmp/prisma-audit-2026-06-16-backend.log 2>&1 & disown` bzw. für's Frontend
  `cd frontend && nohup npm run dev -- -p 3090 > /tmp/prisma-audit-2026-06-16-frontend.log 2>&1
  & disown`.
- API-Key für geschützte Endpoints: `API_KEY=$(grep "^API_KEY=" .env | cut -d= -f2-)`, dann
  Header `-H "X-API-Key: $API_KEY"`. **Niemals den Wert von API_KEY/ANTHROPIC_API_KEY/etc. in
  Findings-Dateien, Commits oder Chat-Ausgabe im Klartext wiedergeben** — nur Variablennamen
  referenzieren.
- LLM-Calls (Claude/VoyageAI) sind echtes Geld. Jede Funktion, die einen LLM-Call auslöst
  (Memo-Generierung, Chat, Discovery-Antworten, Multi-Agent Deep-Dive), **maximal 1-2x** pro
  Edge-Case aufrufen, nicht in Schleifen.
- Findings-Datei-Format (für Tasks 1-7, jeweils eigene Datei — vermeidet Schreibkonflikte
  zwischen parallelen Agents):

```markdown
# Audit-Findings — <Block-Name> (2026-06-16)

## Getestete Funktionen
- <Funktion/Endpoint>: OK | BUG | UX-ISSUE | PERF-ISSUE

## Befunde

### F-<Block-Kürzel>-<N> — <Kurztitel>
- **Bereich:** Funktional | UX | Performance
- **Schweregrad:** Kritisch | Wichtig | Nice-to-have
- **Ort:** <Datei:Zeile oder Endpoint>
- **Beschreibung:** <was ist falsch/schlecht>
- **Reproduktion:** <exakte Schritte/Request>
- **Vorschlag:** <konkreter Fix-Ansatz>
```

- Jeder Task endet mit `git add docs/audit-findings/2026-06-16-<block>.md && git commit -m
  "docs(audit): findings für <block>"` auf dem aktuellen Worktree-Branch.

---

### Task 0: Findings-Infrastruktur anlegen

**Files:**
- Create: `docs/audit-findings/.gitkeep`

- [ ] **Schritt 1:** Verzeichnis anlegen

```bash
mkdir -p docs/audit-findings && touch docs/audit-findings/.gitkeep
```

- [ ] **Schritt 2:** Commit

```bash
git add docs/audit-findings/.gitkeep
git commit -m "chore(audit): prepare findings directory"
```

---

### Task 1: Phase A1 — Discovery & Onboarding

**Files:**
- Create: `docs/audit-findings/2026-06-16-discovery-onboarding.md`
- Reference (lesen, nicht ändern): `frontend/app/start/page.tsx`, `frontend/app/discover/*.tsx`,
  `backend/interfaces/rest/routers/discovery.py` (oder äquivalent), `backend/interfaces/rest/
  schemas/investor_profile.py`

**Abgedeckte Endpoints:** `POST /api/v1/discovery/session`, `POST /api/v1/discovery/answer`,
`POST /api/v1/discovery/complete`, `GET /api/v1/discover`, `GET/POST /api/v1/profile`.

- [ ] **Schritt 1:** Frontend-Code der Onboarding-Flow lesen (`frontend/app/start/page.tsx`,
  `frontend/app/discover/discover-client.tsx`), um die echten `data-testid`-Selektoren und den
  5-Schritt-Ablauf (Beruf, Ziel, Risiko, Brands, Abschluss) zu kennen.

- [ ] **Schritt 2:** Happy Path per Playwright live durchspielen. Env für Playwright:
  `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3090 PLAYWRIGHT_API_URL=http://localhost:
  8090 PLAYWRIGHT_NO_WEBSERVER=1 npx playwright test e2e/01-universe.spec.ts --headed=false`
  (zur Kontrolle, dass Baseline grün ist) — danach eigenes Skript unter
  `frontend/e2e/_audit-tmp-discovery.spec.ts` schreiben, das **ohne** den
  `prisma_onboarding`-Cookie aus `playwright.config.ts` startet (eigener `test.use({ storageState:
  { cookies: [], origins: [] } })`), auf `/start` navigiert, durch alle 5 Schritte klickt,
  Screenshots nach jedem Schritt nach `/tmp/audit-screenshots/discovery-step-N.png` schreibt.

- [ ] **Schritt 3:** Edge Cases direkt über die API testen (schneller als UI für Grenzfälle):
  - Leere Antwort: `curl -s -X POST http://localhost:8090/api/v1/discovery/answer -H "Content-Type: application/json" -d '{"session_id":"<id>","question_id":"beruf","answer":""}'`
  - Ungültige `session_id` (zufällige UUID): erwartetes Verhalten prüfen (404 vs. 500 — 500 wäre ein Bug)
  - Sehr langer String (>1000 Zeichen) als Antwort auf ein Freitext-Feld
  - Doppeltes `complete` auf dieselbe Session (Idempotenz?)

- [ ] **Schritt 4:** UX bewerten: Lädt jeder Schritt ohne Layout-Sprung? Gibt es eine
  Fortschrittsanzeige? Was passiert bei Browser-Reload mitten im Flow (Step 3)? Mobile-Breite
  375px in Playwright (`viewport: { width: 375, height: 812 }`) — bricht etwas um?

- [ ] **Schritt 5:** Temporäre Playwright-Datei wieder löschen (`rm
  frontend/e2e/_audit-tmp-discovery.spec.ts`), Screenshots bleiben unter `/tmp/audit-screenshots/`
  für die Konsolidierung in Task 8.

- [ ] **Schritt 6:** Findings nach Template in
  `docs/audit-findings/2026-06-16-discovery-onboarding.md` schreiben, committen.

---

### Task 2: Phase A2 — Rankings, Stock-Deep-Dive, Research, Watchlist

**Files:**
- Create: `docs/audit-findings/2026-06-16-rankings-deepdive.md`
- Reference: `frontend/app/dashboard/`, `frontend/app/rankings/`, `frontend/app/stocks/`,
  `frontend/app/decision/`, `frontend/app/research/`, `frontend/app/watchlist/`

**Abgedeckte Endpoints:** `/api/v1/runs*`, `/api/v1/stocks*`, `/api/v1/memos*`,
`/api/v1/decisions*`, `/api/v1/ml/predict`.

- [ ] **Schritt 1:** Bestehenden Run/Ranking abrufen: `API_KEY=$(grep "^API_KEY=" .env | cut
  -d= -f2-); curl -s -H "X-API-Key: $API_KEY" http://localhost:8090/api/v1/runs | python3 -m
  json.tool`. Falls leer: einen Run für `SMI-20` auslösen (Endpoint/Skript im Code suchen, z. B.
  `backend/application/services/ranking_run_service.py` für den Trigger-Mechanismus) und
  abwarten.

- [ ] **Schritt 2:** `/dashboard` und `/rankings` im Browser (Playwright, Viewport 1280x800)
  öffnen, prüfen: Tabelle sortierbar? CSV-Export funktioniert (`docs` erwähnen "Rankings
  Sortierung CSV-Export" Playwright-Test existiert bereits unter `frontend/e2e/` — diesen Test
  zuerst laufen lassen: `PLAYWRIGHT_BASE_URL=http://localhost:3090 PLAYWRIGHT_API_URL=http://
  localhost:8090 PLAYWRIGHT_NO_WEBSERVER=1 npx playwright test -g "CSV-Export"`).

- [ ] **Schritt 3:** Für einen Ticker aus `SMI-20` (z. B. `NESN`) und einen aus `Tech-Big-12`
  (z. B. `AAPL`) je ein Memo generieren: `curl -s -X POST -H "X-API-Key: $API_KEY" -H
  "Content-Type: application/json" http://localhost:8090/api/v1/memos/generate -d
  '{"stock_id":"<id>","run_id":"<run_id>","language":"de"}'` — **max. 2 Aufrufe**, da LLM-Call.
  Im Browser `/stocks/NESN` (oder analoge Route, im Code `frontend/app/stocks/` prüfen wie der
  Pfad genau aufgebaut ist, z. B. `/stocks/[ticker]`) öffnen, Deep-Dive/Memo ansehen.

- [ ] **Schritt 4:** Edge Cases: ungültiger Ticker (`/api/v1/stocks/XXXXX`, erwartet 404 nicht
  500), Memo für nicht-existenten `run_id` (UUID erfinden), `/api/v1/decisions/live` ohne
  vorherigen Run.

- [ ] **Schritt 5:** UX: Wie wird ein laufender Memo-Batch-Job (`/api/v1/memos/jobs/{job_id}`)
  im Frontend signalisiert (Spinner, Polling)? Was zeigt die UI, wenn `is_error=true` im Memo
  zurückkommt (vgl. `MemoErrorCard` Component, bereits getestet in Unit-Tests — live im Browser
  reproduzieren, z. B. durch absichtlich ungültigen `run_id`)?

- [ ] **Schritt 6:** `/research` und `/watchlist` analog kurz durchklicken (Happy Path +
  leerer Zustand, z. B. Watchlist ohne Einträge).

- [ ] **Schritt 7:** Findings committen wie im gemeinsamen Format beschrieben.

---

### Task 3: Phase A3 — Portfolio, Macro, Fonds, Steuer

**Files:**
- Create: `docs/audit-findings/2026-06-16-portfolio-macro-fonds-steuer.md`
- Reference: `frontend/app/portfolio/`, `frontend/app/fonds/`, `frontend/app/steuer/`

**Abgedeckte Endpoints:** `/api/v1/portfolio/allocate`, `/api/v1/portfolio/rebalance`,
`/api/v1/portfolio/monte-carlo`, `/api/v1/macro/context`, `/api/v1/macro/score/{ticker}`,
`/api/v1/fonds`, `/api/v1/fonds/vergleich`, `/api/v1/steuer/einschaetzung`.

- [ ] **Schritt 1:** Happy Path `/portfolio`: ein realistisches Portfolio eingeben (3-5 SMI-20-
  Ticker, Stückzahlen), Rebalancing-Empfehlung ansehen. Dann **Stress-Eingabe**: 50+ Positionen
  in einem Portfolio (Skript generieren, das ein JSON-Array mit 50 Tickern + Mengen baut und via
  `curl -X POST http://localhost:8090/api/v1/portfolio/allocate ...` sendet) — Antwortzeit
  stoppen (`time curl ...`), Ergebnis auf Plausibilität prüfen.

- [ ] **Schritt 2:** Monte-Carlo-Simulation auslösen (`/api/v1/portfolio/monte-carlo`),
  Antwortzeit messen — das ist laut Code rechenintensiv, möglicher Performance-Hotspot für
  Task 6.

- [ ] **Schritt 3:** `/macro/context` und `/macro/score/{ticker}` für 2-3 Ticker abrufen, im
  Frontend (`/dashboard` enthält laut README Makro-Kontext) prüfen ob die Werte konsistent mit
  dem Rohdaten-Call sind.

- [ ] **Schritt 4:** `/fonds/vergleich`: Vergleich mit ungültigem Fonds-Identifier testen
  (erwartet sauberer 4xx-Fehler).

- [ ] **Schritt 5:** `/steuer/einschaetzung` für einen Ticker, der laut 3a-Eligibility-Filter
  NICHT zugelassen ist, vs. einen der zugelassen ist — prüfen ob UI das unterschiedlich
  kommuniziert.

- [ ] **Schritt 6:** UX: Sind Zahlen einheitlich formatiert (CHF, %, Dezimaltrennzeichen
  de-CH)? Negative Werte (Verlust) farblich klar erkennbar?

- [ ] **Schritt 7:** Findings committen.

---

### Task 4: Phase A4 — Backtest, Crypto, Universes

**Files:**
- Create: `docs/audit-findings/2026-06-16-backtest-crypto-universes.md`
- Reference: `frontend/app/backtest/`, `frontend/app/crypto/`, `frontend/app/universes/`

**Abgedeckte Endpoints:** `/api/v1/backtests*`, `/api/v1/backtest/signal-validation/{ticker}`,
`/api/v1/crypto/*`, `/api/v1/universes*`.

- [ ] **Schritt 1:** Backtest gegen SMI-Benchmark für `SMI-20`-Universe auslösen, Laufzeit
  stoppen, Ergebnis (Sharpe, Max Drawdown, annualisierte Rendite) auf Plausibilität prüfen
  (Sharpe z. B. nicht NaN/Infinity — vgl. K-9 aus altem Audit zu Backtest-Series-Typen,
  stichprobenartig verifizieren, dass `prisma/universe/benchmark` als `number[]` ankommen, nicht
  als Strings).

- [ ] **Schritt 2:** Crypto-Modul: `/crypto` im Browser, Simple- UND Pro-Mode, Fear&Greed-Gauge,
  mind. 2 Signal-Karten ansehen. Edge Case: `CRYPTO_FEATURE_ENABLED=false` testen — `.env`
  temporär in einer Kopie ändern und Backend neu starten? **Nein** — stattdessen den Code in
  `backend/config.py` lesen und nur per Reasoning/Code-Review prüfen, ob die UI bei
  `feature_enabled=false` (z. B. via direktem API-Test `GET /api/v1/crypto/market` Header-Trick
  falls vorhanden) sauber degradiert; kein Neustart des gemeinsamen Stacks nötig (würde Phase A
  für andere Agents stören).

- [ ] **Schritt 3:** Neues Universe per Wizard (`/universes/wizard`) anlegen (echter LLM-Call —
  max. 1x), danach `/universes/new` (manueller Pfad) ein zweites Mal mit 1-2 Tickern anlegen.
  Edge Case: Universe-Name, der bereits existiert (UNIQUE-Constraint — siehe Test-Flakiness-Fix
  aus PR #200, prüfen ob Fehlermeldung im Frontend jetzt verständlich ist statt rohem 500).

- [ ] **Schritt 4:** `/universes/{id}/sync` für ein Universe mit einem ungültigen/delisteten
  Ticker (z. B. frei erfundenes ISIN-ähnliches Symbol) auslösen — sauberer Fehler oder Crash?

- [ ] **Schritt 5:** Findings committen.

---

### Task 5: Phase A5 — News, Alerts, Chat, Reports/PDF, Decision-Audit-Trail, Admin

**Files:**
- Create: `docs/audit-findings/2026-06-16-news-alerts-chat-reports.md`
- Reference: `frontend/app/news/`, `frontend/app/alerts/`, `backend/interfaces/rest/routers/
  chat.py`, `backend/interfaces/rest/routers/alerts.py`, Report/PDF-Export-Code (suchen, z. B.
  `backend/.../reports/` oder im `runs/{run_id}/export`-Handler), `backend/interfaces/rest/
  routers/decisions.py` (Audit-Trail).

**Abgedeckte Endpoints:** `/api/v1/news/ingest`, `/api/v1/news/retrieve`, `/api/v1/alerts*`,
`/api/v1/chat`, `/api/v1/runs/{run_id}/export`, `/api/v1/decisions/{ticker}/audit`,
`/api/v1/admin/costs`, `/api/v1/rag/*`.

- [ ] **Schritt 1:** `/news` im Browser, dann `POST /api/v1/news/ingest` mit einer echten
  News-URL oder Testtext auslösen (prüfen ob das Voyage-Embeddings nutzt — max. 1x), danach
  `/api/v1/news/retrieve` mit passender Query, Ergebnis-Relevanz beurteilen.

- [ ] **Schritt 2:** `/alerts`: Alert anlegen über die UI (Happy Path). **Sicherheits-Edge-Case**
  gezielt gegen K-7 (Webhook-SSRF, sollte laut altem Audit gefixt sein) erneut testen:
  `curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json"
  http://localhost:8090/api/v1/alerts -d '{"channel":"WEBHOOK","target":"http://169.254.169.254/latest/meta-data/","ticker":"NESN","condition":"PRICE_ABOVE","threshold":1}'`
  — erwartet: 4xx-Validierungsfehler, NICHT 200/201. Wenn 200/201 zurückkommt: **Kritischer
  Regressions-Fund**, sofort in Findings mit Schweregrad Kritisch vermerken.

- [ ] **Schritt 3:** Chat-Feature im Frontend lokalisieren (in `frontend/app/` nach Komponenten
  suchen, die `/api/v1/chat` aufrufen — `grep -rl "api/v1/chat" frontend/app`), Happy-Path-Frage
  stellen (max. 2 Anfragen, echter Claude-Call). Edge Case: leere Nachricht senden, sehr lange
  Nachricht (>4000 Zeichen) senden — Backend sollte validieren, nicht ungebremst an Claude
  weiterleiten (Kostenrisiko).

- [ ] **Schritt 4:** Report/PDF-Export: `curl -s -H "X-API-Key: $API_KEY" -o /tmp/audit-report.pdf
  -w "%{http_code}\n" http://localhost:8090/api/v1/runs/<run_id>/export` — prüfen ob gültiges
  PDF (`file /tmp/audit-report.pdf` sollte "PDF document" zeigen). Falls WeasyPrint auf diesem
  Mac fehlt: erwartet laut PR #195-Fix ein 503, nicht 500 — beides als Finding vermerken (503
  bedeutet Feature ist hier nicht testbar, kein Bug).

- [ ] **Schritt 5:** `/api/v1/decisions/{ticker}/audit` für einen Ticker mit existierendem Run
  abrufen, Vollständigkeit der Audit-Kette prüfen (jede Entscheidung nachvollziehbar?).

- [ ] **Schritt 6:** `/api/v1/admin/costs` abrufen — prüfen ob Budget-Cap-Zähler nach den
  LLM-Calls aus den vorherigen Schritten plausibel gestiegen ist (Cross-Check des Cost-Trackers).

- [ ] **Schritt 7:** Findings committen.

---

### Task 6: Phase B — Performance & Last-Test (exklusiver Stack)

**Files:**
- Create: `docs/audit-findings/2026-06-16-performance.md`
- Create (temporär, nicht committen): `/tmp/audit-locust/locustfile.py`

- [ ] **Schritt 1:** Eigene, exklusive Infrastruktur (separat von Phase A, andere Ports/DB) im
  selben Worktree starten — Ports vorher live prüfen, da andere Sessions parallel laufen:

```bash
for p in 5434 8092; do lsof -nP -iTCP:$p -sTCP:LISTEN | grep LISTEN && echo "PORT $p BUSY (anderen Port wählen)" || echo "PORT $p free"; done
docker volume create prisma-perf-pgdata
docker run -d --name prisma-db-perf -e POSTGRES_USER=prisma -e POSTGRES_PASSWORD=prisma \
  -e POSTGRES_DB=prisma -p 5434:5432 -v prisma-perf-pgdata:/var/lib/postgresql/data \
  -v "$(pwd)/scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro" \
  pgvector/pgvector:pg16
# warten bis healthy:
until docker exec prisma-db-perf pg_isready -U prisma -d prisma >/dev/null 2>&1; do sleep 1; done
```

- [ ] **Schritt 2:** Eigene `.env`-Kopie mit `DATABASE_URL` auf Port 5434, Backend auf Port 8092
  starten (gleiches Muster wie Phase A, siehe "Gemeinsame Spielregeln"), Migrationen + Seed
  (`alembic upgrade head`, `python scripts/seed_smi_universe.py`, `python
  scripts/seed_tech_catalog.py` mit `DATABASE_URL` exportiert auf die 5434-Verbindung).

- [ ] **Schritt 3:** Locust installieren und Lastprofil gegen **LLM-freie** Endpoints fahren
  (kein Kostenrisiko):

```bash
source .venv/bin/activate && uv pip install locust
mkdir -p /tmp/audit-locust
cat > /tmp/audit-locust/locustfile.py <<'PYEOF'
from locust import HttpUser, task, between

API_KEY = "<aus .env, NICHT hardcoden — siehe Hinweis unten>"

class PrismaUser(HttpUser):
    wait_time = between(0.1, 1.0)

    @task(3)
    def list_stocks(self):
        self.client.get("/api/v1/stocks", headers={"X-API-Key": API_KEY})

    @task(2)
    def get_universes(self):
        self.client.get("/api/v1/universes", headers={"X-API-Key": API_KEY})

    @task(1)
    def stock_factsheet(self):
        self.client.get("/api/v1/stocks/NESN/factsheet", headers={"X-API-Key": API_KEY})
PYEOF
```

  Vor dem Schreiben den Platzhalter `API_KEY = "..."` durch den echten Wert ersetzen — dafür
  **nicht** den Wert in den Chat/Findings ausgeben, sondern direkt per Shell einsetzen:

```bash
API_KEY_VAL=$(grep "^API_KEY=" .env | cut -d= -f2-)
sed -i.bak "s#<aus .env, NICHT hardcoden — siehe Hinweis unten>#${API_KEY_VAL}#" /tmp/audit-locust/locustfile.py
rm /tmp/audit-locust/locustfile.py.bak
```

- [ ] **Schritt 4:** Last in steigenden Stufen fahren, jede Stufe 60s, Ergebnisse (p50/p95/p99,
  Error-Rate) notieren:

```bash
cd /tmp/audit-locust
for USERS in 5 20 50 100 200; do
  locust -f locustfile.py --headless -u $USERS -r 10 --run-time 60s \
    --host http://localhost:8092 --csv "run-${USERS}u" --only-summary
done
```

- [ ] **Schritt 5:** Sobald Latenz (p95) > 2s oder Error-Rate > 5% auftritt: Breaking Point
  notieren, dann am Backend-Prozess der Phase-B-Instanz nachsehen, welche Query/welcher Call
  blockiert — `EXPLAIN ANALYZE` für die Hot-Query aus `backend/infrastructure/persistence/
  repositories/stock_repository.py` (oder analoge Datei für `/api/v1/stocks`) direkt über
  `docker exec -it prisma-db-perf psql -U prisma -d prisma -c "EXPLAIN ANALYZE SELECT ..."`
  laufen lassen (echtes Query aus dem Repository-Code übernehmen, nicht raten).

- [ ] **Schritt 6:** Code-Scan auf blockierende sync-Calls im Event-Loop, die noch nicht durch
  `asyncio.to_thread` abgesichert sind (K-10/K-11 aus altem Audit waren bereits gefixt — prüfen
  ob es **neue** Stellen seither gibt, z. B. im Crypto-Modul, das nach dem alten Audit entstand):

```bash
grep -rn "yf\.\|requests\.get\|requests\.post" backend/application backend/infrastructure | grep -v "to_thread\|test"
```

  Jeden Treffer einzeln prüfen: läuft er in einem `async def` ohne `asyncio.to_thread`-Wrapper?
  Falls ja → Finding mit Schweregrad Kritisch (blockiert den ganzen Server für alle Nutzer).

- [ ] **Schritt 7:** Frontend-Bundle-Größe checken: `cd frontend && npm run build 2>&1 | tail -40`
  — auf Next.js-Warnung zu großen Bundles/Chunks achten (`First Load JS` Werte pro Route).

- [ ] **Schritt 8:** Phase-B-Infrastruktur aufräumen (NICHT die Phase-A-Instanz anfassen):

```bash
docker rm -f prisma-db-perf
docker volume rm prisma-perf-pgdata
pkill -f "uvicorn.*--port 8092"
```

- [ ] **Schritt 9:** Findings (Breaking Points, Bottlenecks, Bundle-Size-Auffälligkeiten) nach
  Template in `docs/audit-findings/2026-06-16-performance.md` schreiben, committen.

---

### Task 7: Phase C — Render Smoke-Test (read-only)

**Files:**
- Create: `docs/audit-findings/2026-06-16-render-smoketest.md`

- [ ] **Schritt 1:** Health-Check:

```bash
curl -s -o /dev/null -w "status=%{http_code} time=%{time_total}s\n" https://prisma-v2-backend.onrender.com/health
curl -s -o /dev/null -w "status=%{http_code} time=%{time_total}s\n" https://prisma-v2-frontend.onrender.com
```

  Hinweis: Render-Free-Tier-Instanzen schlafen bei Inaktivität — der erste Call kann 30-60s
  dauern (Cold Start). Das ist selbst ein Usability-Finding wert, kein Bug.

- [ ] **Schritt 2:** Genau 2-3 lesende Endpoints ohne Auth-Bedarf oder mit dem Produktions-
  `API_KEY` (falls dem User bekannt — sonst auslassen, NICHT raten/brute-forcen) prüfen, z. B.
  `GET https://prisma-v2-backend.onrender.com/api/v1/universes`. **Keine** POST/PUT/DELETE-Calls
  gegen Render, **keine** Lastwiederholung.

- [ ] **Schritt 3:** `APP_VERSION` aus `/health` mit dem aktuellen `pyproject.toml`-`version`-
  Feld im Worktree vergleichen — Drift bedeutet Render hat noch nicht den neuesten `main`-Stand
  deployed (ggf. wegen des bekannten Blockers aus PR #200: fehlende
  `RENDER_V2_DEPLOY_HOOK_*`-Secrets).

- [ ] **Schritt 4:** Findings committen.

---

### Task 8: Konsolidierung der Findings

**Files:**
- Create: `docs/usability-performance-audit-2026-06-16.md`
- Read: alle Dateien unter `docs/audit-findings/2026-06-16-*.md`

- [ ] **Schritt 1:** Alle 6 Findings-Dateien aus Task 1-7 einlesen, jeden Befund einer von drei
  Kategorien zuordnen: Kritisch (Sicherheit/Datenverlust/Server-Crash/falsche Finanzzahlen),
  Wichtig (Funktion kaputt aber kein Sicherheitsrisiko, klare UX-Verschlechterung), Nice-to-have
  (kosmetisch).

- [ ] **Schritt 2:** Konsolidiertes Dokument nach folgendem Schema schreiben (gleiche Struktur
  wie `docs/audit-fix-plan-2026-06-13.md`, damit das Team das gewohnte Format wiedererkennt):

```markdown
# Usability-, Funktions- & Performance-Audit — 2026-06-16

Branch: `worktree-usability-performance-audit-2026-06-16`
Erstellt durch: Paralleler Multi-Agenten-Audit (Discovery, Rankings/Deep-Dive,
Portfolio/Macro/Fonds/Steuer, Backtest/Crypto/Universes, News/Alerts/Chat/Reports, Performance,
Render-Smoke-Test)
Status: 🔄 IN PROGRESS

## Übersicht

| Bereich | Kritisch | Wichtig | Nice-to-have |
|---|---|---|---|
| ... (pro Block eine Zeile, Summen aus Task 1-7) ... |

## KRITISCHE FIXES

### K-<N> — <Titel>
- **Datei/Endpoint:** ...
- **Problem:** ...
- **Fix:** ...
- **Status:** ⬜ TODO

(... usw. für Wichtig/Nice-to-have analog zu W-<N> / I-<N> ...)
```

- [ ] **Schritt 3:** Commit:

```bash
git add docs/usability-performance-audit-2026-06-16.md
git commit -m "docs(audit): konsolidiertes Usability-/Performance-Audit 2026-06-16"
```

- [ ] **Schritt 4:** Dem User eine kurze Zusammenfassung geben (Anzahl Kritisch/Wichtig/Nice-to-
  have, die 3-5 schwerwiegendsten Funde) **bevor** Task 9 (Fixes) gestartet wird — das ist der
  einzige Punkt im Plan, an dem aktiv auf Bestätigung gewartet werden sollte, falls die Liste
  ungewöhnlich lang/teuer wird (z. B. >15 kritische Funde, die viele PRs bedeuten würden).

---

### Task 9: Fix-Implementierung & PRs

**Files:** variabel, abhängig von Task-8-Ergebnis.

- [ ] **Schritt 1:** Kritische und Wichtige Funde aus `docs/usability-performance-audit-2026-06-
  16.md` nach Code-Nähe gruppieren (z. B. alle Findings, die dieselbe Datei/denselben Bereich
  betreffen, in eine Gruppe). Jede Gruppe wird zu genau einem Branch + PR.

- [ ] **Schritt 2:** Vor JEDEM neuen Fix-Branch den lokalen `main`-Stand aktualisieren (heute
  bereits zweimal während der Audit-Laufzeit gemerged worden — strict-mode auf `main` verlangt
  aktuellen Stand):

```bash
git fetch origin
git checkout -b fix/<thema>-2026-06-16 origin/main
```

- [ ] **Schritt 3:** Für jeden Fix striktes TDD: zuerst einen Test schreiben, der den Bug
  reproduziert (roter Test), dann den minimalen Fix, dann grün. Beispielmuster (konkretes
  Beispiel hängt vom tatsächlichen Fund ab — Pflicht ist: jeder Fix hat einen neuen oder
  angepassten Test, der ohne den Fix fehlschlägt):

```bash
# Beispielablauf, X = Name des Fixes
pytest backend/tests/unit/<passender_pfad>/test_X.py -v   # erwartet: FAIL
# Fix implementieren
pytest backend/tests/unit/<passender_pfad>/test_X.py -v   # erwartet: PASS
ruff format backend/ && ruff check backend/ && mypy backend/
```

  Für Frontend-Fixes analog mit `npx vitest run <pfad>` und `npm run lint`.

- [ ] **Schritt 4:** In `docs/usability-performance-audit-2026-06-16.md` den Status der
  gefixten Punkte von `⬜ TODO` auf `✅ Erledigt` setzen, im selben Commit wie der Fix.

- [ ] **Schritt 5:** Push + PR gegen `main`:

```bash
git push -u origin fix/<thema>-2026-06-16
gh pr create --repo don69andrea/prisma-v2 --base main --title "fix: <thema> (Usability/Perf-Audit 2026-06-16)" --body "Befund(e): <Liste der K-/W-Nummern>. Siehe docs/usability-performance-audit-2026-06-16.md.

## Test plan
- [x] <relevanter Testbefehl> grün
🤖 Generated with Claude Code"
```

- [ ] **Schritt 6:** Nach jedem gemergten PR alle noch offenen eigenen Fix-Branches auf den
  neuen `main`-Stand bringen (`git fetch origin && git merge origin/main`), bevor der nächste
  PR erstellt wird, um Strict-Mode-Konflikte zu vermeiden.

---

## Self-Review-Notizen (für die Person, die diesen Plan ausführt)

- Spec-Abdeckung: Phase A = Tasks 1-5, Phase B = Task 6, Phase C = Task 7, Phase D =
  Tasks 8-9 — deckt alle Phasen aus dem Design-Spec ab.
- Task 9 kann nicht im Voraus exakten Fix-Code enthalten, weil die Bugs erst in Tasks 1-7
  gefunden werden — bewusste Ausnahme von "kein Platzhalter", da dies ein Audit- und kein
  reines Implementierungsplan ist. Die Methodik (TDD, Branch-Konvention, PR-Format) ist aber
  vollständig konkret vorgegeben.
- Port-/Stack-Zuweisungen (5433/8090/3090 für Phase A, 5434/8092 für Phase B) sind Vorschläge;
  jeder Task prüft Verfügbarkeit live, da auf der Maschine parallele Sessions laufen.
