# Usability-, Funktions- & Performance-Audit — PRISMA V2 (2026-06-16)

## Kontext

PRISMA V2 hat bereits mehrere Audit-Runden durchlaufen: Security/Performance/Contract-Audit
(2026-06-13, 13 kritische Fixes, gemergt), Deep Bug Hunt (2026-06-15, 30 Fixes), Go-Live-Audit
(PR #200, heute gemergt — Funktionstest gegen isolierten Stack: Backend-/Frontend-Suite +
73 Playwright-E2E, alle grün). Was bisher fehlt: ein **unabhängiger End-to-End-Re-Test jeder
Funktion** mit echten API-Keys, eine **dedizierte UX/Usability-Bewertung** und ein **Last-/
Performance-Test, der die App gezielt an ihre Grenzen treibt**.

## Ziele

1. Jede Nutzer-Funktion der App mindestens einmal end-to-end mit echten API-Keys ausführen
   (nicht nur bestehende Test-Suiten laufen lassen, sondern aktiv im Browser/über die API
   durchspielen, inkl. Edge Cases).
2. Usability bewerten: Fehlermeldungen, Ladezustände, Mobile/Responsive, Empty States,
   Konsistenz der Sprache/UI.
3. Performance/Last-Grenzen ermitteln: ab welchem Punkt (Concurrency, Datenvolumen) degradiert
   Latenz/Error-Rate; konkrete Bottlenecks (DB-Queries, blockierende Event-Loop-Calls,
   N+1-Patterns) benennen.
4. Befunde dokumentieren und priorisieren.
5. Fixes/Optimierungen sofort umsetzen: ein Branch + PR pro thematischer Fix-Gruppe, gegen
   `main`, nach bestehendem Team-Workflow.

## Nicht-Ziele

- Keine Lasttests gegen die Render-Production-Instanz (nur read-only Smoke-Checks).
- Keine Wiederholung der bereits abgeschlossenen Security-Audit-Punkte (K-1 bis K-13 aus
  `docs/audit-fix-plan-2026-06-13.md`) — nur stichprobenartig verifizieren, dass sie noch halten.
- Kein Neuschreiben bestehender E2E-Suiten; sie laufen als Baseline mit, sind aber nicht der
  Fokus.

## Umgebung

Isolierter Worktree (`worktree-usability-performance-audit-2026-06-16`, gebrancht von aktuellem
`origin/main` inkl. PR #200 + Crypto-Modul), eigene Postgres-Instanz (Docker, Port 5433, Volume
`prisma-audit-pgdata`), Backend nativ auf Port 8090, Frontend nativ auf Port 3090. Demo-Daten:
SMI-20 + Tech-Big-12 geseedet. Echte API-Keys aus `.env` (Anthropic, VoyageAI, FMP, SendGrid,
CoinGecko) — Tests sparsam fahren, nicht jede LLM-Funktion endlos wiederholen (Budget-Cap
beachten). Baseline verifiziert: 802/802 Backend-Unit-Tests, 234/234 Frontend-Tests grün.

Grund für eigene Ports/DB: Auf der Maschine laufen parallel mind. 2 weitere aktive Sessions
(eigene Checkouts unter `/Users/andreapetretta/prisma-v2` auf Port 8000/5432 und
`/private/tmp/prisma-v2` auf Port 8001) — keine Kollision, keine gemeinsame Datenbasis.

## Phasen

### Phase A — Funktional + UX (parallel, mehrere Agents, EIN gemeinsamer Stack)

Jeder Agent übernimmt einen Feature-Block, testet jede Aktion live (Browser via Playwright MCP/
Code oder direkte API-Calls) und bewertet UX nebenbei. Pflicht je Block: Happy Path, mind. 2
Edge Cases (leere Eingabe, riesige/ungültige Eingabe, fehlende Daten), Fehlerdarstellung im UI,
mobile Breite (375px) prüfen.

Feature-Blöcke:
- **A1 Discovery & Onboarding** — 5-Schritt-Conversational-Flow, Investor-Profil, Empfehlungen
- **A2 Rankings & Stock-Deep-Dive** — Dashboard BUY/HOLD/SELL, Memo-Generierung, Multi-Agent
  Deep-Dive (Fundamentals/Sentiment/Synthesizer), SHAP-Erklärungen
- **A3 Portfolio, Macro, Fonds, 3a** — Portfolio-Agent (Rebalancing), Macro-Kontext, Fonds vs.
  Einzeltitel-Vergleich, 3a-Eligibility-Filter
- **A4 Backtest & Crypto** — Backtest-Engine vs. SMI-Benchmark, Crypto-Modul (Simple/Pro Mode,
  Fear&Greed, Signale)
- **A5 Chat, Reports, Decision Audit Trail, Alerts** — LLM-Chat, PDF-Export (WeasyPrint), Audit
  Trail, Alert-Engine (inkl. Webhook-Validierung)

Jeder Agent schreibt seine Befunde in einen eigenen Abschnitt der gemeinsamen Findings-Datei
(siehe Deliverables) — keine gegenseitige Überschreibung, klar getrennte Sections.

### Phase B — Performance & Last (exklusiv, 1-2 Agents, eigener frischer Stack)

Eigener Postgres + Backend-Prozess (weitere neue Ports), damit Messwerte nicht durch Phase-A-
Traffic verzerrt werden. Werkzeuge: `locust` (Python, kein System-Package nötig — weder `k6` noch
`locust` waren auf der Maschine vorinstalliert; `locust` lässt sich direkt per `uv pip install`
in das bestehende venv holen) für HTTP-Last gegen Hot-Endpoints (`/api/v1/runs`,
`/api/v1/stocks`, `/api/v1/decisions/live`, `/api/v1/discover`), `EXPLAIN ANALYZE` auf
Hot-Queries, Check auf blockierende sync-Calls im
Event-Loop (yfinance, requests ohne `asyncio.to_thread`), Frontend-Bundle-Size/Lighthouse.
Ziel: Breaking Point (Latenz-Anstieg, Error-Rate) bei steigender Concurrency dokumentieren, dann
konkrete Bottlenecks im Code benennen.

### Phase C — Render Smoke-Test (read-only, 1 Agent)

Wenige gezielte GET-Requests gegen die deployte Render-Instanz (Health, ein bis zwei
Lese-Endpoints), kein Last-Test, keine Schreiboperationen. Ziel: sicherstellen, dass Produktion
nicht bereits in einem the abweichenden/kaputten Zustand ist, den ein rein lokaler Test nicht
sehen würde (z. B. Env-Var-Drift, Render-spezifische Probleme).

### Phase D — Konsolidierung + Fixes

Findings aus A+B+C werden zu einem neuen Dokument `docs/usability-performance-audit-2026-06-16.md`
konsolidiert (eigener Name, keine Kollision mit den bestehenden Audit-Docs von heute/letzter
Woche), priorisiert (Kritisch/Wichtig/Nice-to-have, analog zum bestehenden Schema). Danach:
Fixes nach Thema gruppiert, je Gruppe ein Agent auf eigenem Branch (`fix/<thema>-2026-06-16`)
→ PR gegen `main` nach bestehendem Workflow (CI muss grün sein, 1 Review erforderlich da
`enforce_admins: true`).

## Deliverables

- `docs/usability-performance-audit-2026-06-16.md` — alle Findings, priorisiert, mit Status-Spalte
- N PRs gegen `main`, je eine thematische Fix-Gruppe
- Dieses Spec-Dokument + der nachfolgende Implementierungsplan (committed)

## Risiken / Mitigationen

- **Port-/DB-Kollision mit anderen aktiven Sessions** → bereits durch isolierte Ports (5433,
  8090, 3090) und eigenes Docker-Volume gelöst.
- **Reale API-Kosten (Claude/VoyageAI) durch Last-Tests** → Last-Tests in Phase B zielen primär
  auf Endpoints ohne LLM-Call oder nutzen Mocks für den LLM-Layer, um Kosten zu begrenzen.
- **Parallele Merges in `main` während der Arbeit** (heute bereits zweimal passiert) → vor jedem
  PR Branch auf aktuellen `main` rebasen/mergen (strict-mode Pflicht).
- **Mehrere Agents schreiben gleichzeitig in dieselbe Findings-Datei** → jeder Agent bekommt
  eine eigene Datei pro Feature-Block (`docs/audit-findings/2026-06-16-<block>.md`), die in
  Phase D zusammengeführt werden — vermeidet Merge-Konflikte unter Agents.
