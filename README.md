# PRISMA

> Quantitatives Stock-Selection-Tool mit LLM-gestützter Research-Narrative und MCP-Integration.

PRISMA zerlegt Aktien in analytische Dimensionen — wie ein optisches Prisma weisses Licht in sein Spektrum zerlegt. Fünf quantitative Modelle in vier Kategorien (Quality, Trend, Value, Risk) bewerten jedes Unternehmen eines gewählten Universums. Eine Claude-gestützte Narrative Engine erklärt die Rankings in Klartext, ein Multi-Agent-Research-Pipeline produziert Deep-Dive-Dossiers für Top-Aktien, und ein MCP-Server macht PRISMA direkt aus Claude Desktop nutzbar.

**Capstone-Projekt** im Modul *AI-assisted Software Development*, BSc Business Artificial Intelligence, FHNW Hochschule für Wirtschaft, FS 2026. Referenz: PRISMA der Vireos AG.

## Abgabe-Status

Überblick über die zentralen Nachweise und Artefakte des Projekts (Stand: 2026-06-01).

| Kriterium | Status | Nachweis |
|---|---|---|
| **Architektur** | Clean Architecture (4 Schichten: Domain / Application / Interfaces / Infrastructure) | [`docs/specs/2026-04-21-prisma-capstone-design.md`](./docs/specs/2026-04-21-prisma-capstone-design.md) · siehe Architektur-Sektion unten |
| **Tests** | Backend Unit + Integration · Frontend Vitest · Playwright E2E | [`backend/tests/`](./backend/tests) · [`frontend/app/**/__tests__/`](./frontend/app) · [`frontend/e2e/`](./frontend/e2e) |
| **Test-Coverage** | ~94.5% Backend lokal verifiziert (508 Tests, Gate 80%) | [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) — Coverage-Gate-Eintrag |
| **CI** | GitHub Actions: Backend Lint+Tests, Frontend Lint+Build, Frontend E2E (Playwright) | [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) · [Actions-Tab](https://github.com/SheylaSam/prisma-capstone/actions) |
| **Release-Workflow** | Tag `v*` → Docker-Images auf GHCR + GitHub Release mit Auto-Notes | [`.github/workflows/release.yml`](./.github/workflows/release.yml) |
| **CD-Workflow** | `workflow_dispatch` → Render Deploy Hook (Backend / Frontend / beide) | [`.github/workflows/cd-render.yml`](./.github/workflows/cd-render.yml) |
| **Deployment** | Live auf Render (Free-Plan) | Frontend: [prisma-frontend-jrto.onrender.com](https://prisma-frontend-jrto.onrender.com) · Backend: [prisma-backend-7ai7.onrender.com/health](https://prisma-backend-7ai7.onrender.com/health) · Config: [`render.yaml`](./render.yaml) |
| **API-Docs** | OpenAPI/Swagger automatisch generiert (FastAPI) | [prisma-backend-7ai7.onrender.com/docs](https://prisma-backend-7ai7.onrender.com/docs) |
| **AI-Usage-Log** | Reflexion pro PR mit Agent / Patterns / Lehren, Einträge von allen 4 Teammitgliedern | [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) (63 Einträge · 10 Positives + 10 Anti-Patterns + 4 Quer-Patterns mit Evidenz-Links) |
| **Demo-Skript** | Strukturierter Walk-Through für Live-Demo mit Q&A-Prep | [`docs/DEMO-SCRIPT.md`](./docs/DEMO-SCRIPT.md) |

### Demo-Flow

Empfohlener End-to-End-Walk-Through (~10-15min, ausführliches Skript in [`docs/DEMO-SCRIPT.md`](./docs/DEMO-SCRIPT.md)):

**Akt 1 — Universe definieren**
1. **Dashboard** (`/`) — 4 Stats-Karten: Letzter Run, Anzahl Universen, Anzahl Stocks, Top-Pick mit Sweet-Spot-Indikator. Direkt-Link zum Ranking-Form.
2. **Universen** (`/universes`) — vordefinierte Universen sichtbar (per Seed-Skript: Demo-US-5, Tech-Big-12). Weitere lassen sich jederzeit anlegen.
3. **LLM-Wizard** (`/universes/wizard`) — Freitext-Eingabe wie *"Halbleiter und KI-Stocks aus den USA"* → Claude Haiku schlägt Tickers aus der katalogweiten Whitelist vor (keine Halluzinationen), Pre-Filled Form zum Editieren. Nach dem Speichern öffnet ein Dialog direkt den Weg zum Ranking-Start.

**Akt 2 — Ranking + Drilldown**
4. **Rankings** (`/rankings`) — Form zum Run-Start + Liste vergangener Runs.
5. **Ergebnis** (`/rankings/[runId]`) — Top-10-Cards mit Sweet-Spot-Sternen, Bar-Chart der gewichteten Composite-Scores, vollständige Tabelle mit Per-Modell-Rängen + Tooltips pro Modell-Spalte.
6. **Factsheet** (`/rankings/[runId]/stock/[ticker]`) — Klick auf Ticker öffnet 5 Modell-Karten mit Q1-Badges, Kurschart (1 Jahr), strukturiertes Research-Memo (Claude-generiert, Pydantic-validiert) oder "Memo generieren"-Button.

**Akt 3 — Robustheits-Check**
7. **Run-Vergleich** (`/rankings/compare?a=&b=`) — Zwei Runs via Checkbox auswählen → Side-by-Side mit Δ Rank (grün ↑ / rot ↓ / grau ·) und Δ Score. Cross-Universe-Modus zeigt Schnittmenge + Counts (gemeinsam / nur A / nur B).

Optional: **Backtest** (`/backtest`) — Top-N-Picks gegen Benchmark (S&P 500, SMI) simulieren mit Sharpe, MaxDrawdown, annualisierter Rendite.

Selber Flow läuft als Playwright-Tests in CI (`frontend/e2e/`, 7 Spec-Files).

> **Hinweis Free-Tier**: Der Render-Free-Plan schläft Services nach 15 min Inaktivität ein. Erster Request nach Pause kann 30-60s dauern (Cold-Start). Aggressive Browser-Adblocker (uBlock Origin, Brave Shields o.ä.) können Requests zu `*.onrender.com` blocken — Test in Inkognito empfohlen.

## Features

- **Futuristic Loading Screen**: Animierter Ladescreen beim App-Start
- **Universe → Ranking CTA**: Post-Creation-Dialog leitet direkt zum Ranking-Start weiter
- **Backtest Run-Auswahl**: Dropdown-Selektor mit Run-Namen statt UUID-Textfeld
- **Quant Core**: 5 Modelle (Quality Classic, Alpha, Trend Momentum / EWMA, Value Alpha Potential, Diversification / Ledoit-Wolf)
- **LLM-Universe-Wizard**: Claude Haiku schlägt aus Stock-Katalog passende Universen vor — Whitelist-constrained, Pydantic-validiert, keine Halluzinationen
- **Narrative Engine**: LLM-generierte, strukturierte Research-Memos pro Top-Pick (Claude Sonnet + Tool-Use + Pydantic-Schema)
- **Memo-Drilldown**: Klick auf Ticker im Ranking öffnet Factsheet mit dem strukturierten Memo (Stärken, Risiken, Widersprüche zwischen Modellen, One-Liner)
- **Multi-Agent Deep-Dive**: Fundamentals / Sentiment / Synthesizer-Agenten für Top-10
- **MCP-Server**: PRISMA als Tool aus Claude Desktop nutzbar
- **Backtest**: Benchmark-Vergleich mit Sharpe, MaxDD, annualisierter Rendite
- **Run-History + Vergleich**: Vergangene Runs auswählen und Side-by-Side vergleichen (Δ Rank, Δ Score, Same/Cross-Universe-Erkennung)
- **Dashboard-Stats**: 4 Karten + Runs-Tabelle als Startseite
- **Mobile-Responsive**: Header passt sich an <640px-Viewports an (stacked statt cutoff)

## AI-assisted Development

PRISMA wurde durchgehend mit **Claude Code** als primären Coding-Agent entwickelt — von der ersten Architekturentscheidung bis zum letzten Feature. Der Entwicklungs-Workflow ist explizit und reproduzierbar:

### Workflow

```
Brainstorming → Spec-First → Plan-as-Contract → Subagent-Driven Execution → Two-Stage Review → Reflexion
```

1. **Brainstorming** (`superpowers:brainstorming`) — Architekturentscheidungen werden eine nach der anderen mit dem Team durchgespielt, bevor Code entsteht. Keine "Wall of Decisions", sondern eine Frage pro Turn mit Optionen + Empfehlung.
2. **Spec-First** — Jedes Feature startet mit einer Spec in `docs/specs/`. Der Agent schreibt keine Zeile Code ohne Freigabe der Spec. Über 45 Spec-Dokumente im Repo belegen dies.
3. **Plan-as-Contract** (`superpowers:writing-plans`) — Detaillierte Implementationspläne (800–1500 Zeilen) mit verbatim Test-Code, Bash-Befehlen und Commit-Messages pro Step. Ein Plan ist kein Vorschlag, sondern ein Vertrag — Subagents führen ihn aus, ohne Rückfragen.
4. **Subagent-Driven Execution** (`superpowers:subagent-driven-development`) — Frischer Subagent pro Task mit isoliertem Kontext. Kein Kontext-Spill zwischen Tasks. Der Orchestrator-Agent koordiniert, Implementer-Subagents liefern.
5. **Two-Stage Review** — Jeder Task wird nach der Implementierung zweifach geprüft: (1) Spec-Compliance-Review (wurde genau das gebaut, was bestellt war?) und (2) Code-Quality-Review (ist es sauber, wartbar, DRY?). Beide Reviews laufen als separate Subagents.
6. **Reflexion** — Jeder PR mit substantieller AI-Beteiligung landet in `docs/AI-USAGE.md` mit Agent, Scope, Was gut/schlecht lief, und einer konkreten Lektion.

### Agent-Vertrag

[`AGENTS.md`](./AGENTS.md) ist der verbindliche Verhaltensvertrag für alle Coding-Agents in diesem Repo. Er enthält: Coding-Konventionen mit konkreten Dialogen aus 5+ Features, Branch- und Commit-Strategie, TDD-Pflicht für Domain-Code, LLM-Output-Regeln (Pydantic-Schema, Prompt-Caching, kein Freitext), MCP-Layer-Constraints und Sicherheits-Regeln. Claude Code liest `AGENTS.md` + `CLAUDE.md` automatisch zu Sessionbeginn.

### Modell-Routing

| Aufgabe | Modell |
|---|---|
| Architektur-Entscheidungen, Trade-off-Analyse, Brainstorming | Claude Opus |
| Feature-Implementierung, Review-Loops, Integration | Claude Sonnet |
| Schnelle Strukturierungs-Tasks, triviale Schritte, Haiku-Responses | Claude Haiku |

Das Routing folgt ADR-0005: teurere Modelle für Urteil, günstigere für Schreibarbeit — nicht aus Kostengründen, sondern um den Hauptkontext für Entscheidungen freizuhalten.

### 3 AI-Layer im Produkt

PRISMA nutzt AI nicht nur im Entwicklungsprozess, sondern als Kernfunktion des Produkts selbst:

| Layer | Technologie | Funktion |
|---|---|---|
| **1 · Narrative Engine** | Claude Sonnet + Tool-Use + Pydantic-Schema | Strukturierte Research-Memos pro Aktie: One-Liner, Stärken, Risiken, Modell-Widersprüche, Analyst-Interpretation. Output ist Pydantic-validiert — kein Freitext, kein Schema-Drift. |
| **2 · Multi-Agent Deep-Dive** | Fundamentals-Agent + Sentiment-Agent + Synthesizer-Agent | Parallelisierte Dossiers für Top-N Picks. Jeder Agent spezialisiert auf eine Analyse-Dimension, Synthesizer fasst zusammen. |
| **3 · MCP-Server** | MCP SDK (Python) + FastMCP | PRISMA direkt aus Claude Desktop per Natursprache bedienbar — z.B. *"Zeig mir SPI-Titel, die in Quality und Trend Top-20% sind."* |

### Nachweise auf einen Blick

| Was | Wo | Umfang |
|---|---|---|
| AI-Nutzungs-Reflexion | [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) | 63 Einträge, alle 4 Teammitglieder, 24 destillierte Patterns |
| Specs (Spec-First-Nachweis) | [`docs/specs/`](./docs/specs) | 45+ Spec-Dokumente |
| Implementationspläne | [`docs/superpowers/plans/`](./docs/superpowers/plans) | 9 Pläne, je 800–1500 Zeilen |
| Architecture Decision Records | [`docs/adr/`](./docs/adr) | 6 ADRs mit Status-Feld |
| Agent-Vertrag | [`AGENTS.md`](./AGENTS.md) | Coding-Konventionen + Dialoge |

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 · Next.js 14 · Claude API · MCP SDK · pytest + Playwright · GitHub Actions · Docker · Render

## Architektur

Clean Architecture mit vier Schichten — Domain / Application / Interfaces / Infrastructure. Dependency-Rule: innere Schichten kennen äussere nicht. Siehe [`docs/specs/`](./docs/specs) und [`docs/adr/`](./docs/adr).

```
backend/
├── domain/           # Entities, Value Objects, Domain-Rules
├── application/      # Services / Use Cases
├── interfaces/       # REST + MCP
└── infrastructure/   # Persistence, Market-Data-Adapter, LLM-Adapter

frontend/             # Next.js App
tests/                # Unit / Integration / E2E
docs/                 # Specs, ADRs, Agent-Konventionen
```

## Setup

Voraussetzungen: Docker, Docker Compose, Python 3.12+, Node 20+.

```bash
# Repo klonen
git clone https://github.com/SheylaSam/prisma-capstone.git
cd prisma-capstone

# Environment vorbereiten
cp .env.example .env   # ANTHROPIC_API_KEY, DATABASE_URL anpassen

# Services starten
docker compose up -d

# Backend-Dependencies + Migrations (vom Repo-Root ausführen —
# pyproject.toml und alembic.ini liegen im Root, die App importiert via `backend.`)
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.interfaces.rest.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Ausführliche Setup-Anleitung + Troubleshooting: **[docs/getting-started.md](./docs/getting-started.md)**

## Demo-Daten

Der **Stock-Katalog (13 Ticker)** wird automatisch durch die Migrationen geseedet
(`alembic upgrade head`, Migration `0012`) — lokal *und* auf dem Deployment identisch,
und reproduziert sich nach jedem Deploy bzw. DB-Reset. Es ist also kein Skript nötig,
um die Aktien selbst anzulegen.

Die Skripte legen nur die **Universen** (Ticker-Gruppierungen) an:

```bash
# Demo-US-5 (5 Tickers — AAPL/MSFT/GOOGL/NVDA/JPM)
python scripts/seed_demo_universe.py

# Tech-Big-12 (12 Tech-Tickers — empfohlen für reichhaltige Demo)
python scripts/seed_tech_catalog.py
```

Beide Skripte sind idempotent — mehrfaches Ausführen erzeugt keine Duplikate.

Für die Run-Vergleich-Demo: nach Seed mindestens 2 Runs starten (einmal Tech-Big-12, einmal Demo-US-5), damit der Compare-Flow Cross-Universe-Differenzen zeigt.

## RAG-Ingestion (einmalig)

Der RAG-Corpus (SEC-EDGAR 10-K/10-Q → ~4 000 Chunks in pgvector) wird **einmalig** über ein Skript befüllt.
Auf dem Live-System (Render) läuft das im **Shell-Tab** des Backend-Service:

```bash
# Voraussetzung: VOYAGE_API_KEY muss als Environment Variable gesetzt sein (Render → Backend → Environment)
source .venv/bin/activate
python scripts/ingest_filings.py
```

Das Skript ist **idempotent** — mehrfaches Ausführen ist sicher (bereits bekannte URLs werden übersprungen).
Kosten: ca. $0.24 Voyage-Embedding (ADR-0004 §7).

Nach der Ingestion ist `POST /api/v1/rag/retrieve` einsatzbereit:

```bash
curl -X POST https://<backend>/api/v1/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "Apple revenue growth", "k": 5, "ticker": "AAPL"}'
```

## Testen

```bash
pytest                      # Unit + Integration
pytest --cov=backend        # mit Coverage-Report
npx playwright test         # E2E
```

## Dokumentation

- **Design-Spec**: [`docs/specs/2026-04-21-prisma-capstone-design.md`](./docs/specs/2026-04-21-prisma-capstone-design.md) — Gesamtarchitektur, Domain-Modell, 5 Quant-Modelle, Test-Strategie, CI/CD, Bewertungsraster
- **Architecture Decision Records**: [`docs/adr/`](./docs/adr) — 6 ADRs (Tech-Stack, LLM-Provider, Narrative-Engine, Multi-Agent, Datenquellen, Quant-Modelle-Redesign), je mit Kontext / Entscheidung / Konsequenzen / Status
- **Implementationspläne**: [`docs/superpowers/plans/`](./docs/superpowers/plans) — 9 detaillierte Pläne (800–1500 Zeilen) als Plan-as-Contract für Subagent-Driven-Execution
- **Agent-Konventionen**: [`AGENTS.md`](./AGENTS.md) — verbindlicher Verhaltensvertrag für alle Coding-Agents
- **Contribution-Guidelines**: [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **AI-Nutzungs-Reflexion**: [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) — 63 Einträge, laufend geführt während des Projekts

## Team

Capstone-Team FHNW FS 2026:

| Rolle | Verantwortung |
|---|---|
| Quant Core | Finanzmathematik, Datenadapter, Backtest |
| AI Engineer | LLM-Integration, Multi-Agent, MCP |
| Platform | Architektur, API, CI/CD, Deployment |
| Frontend & Demo | UI, E2E-Tests, Doku, Präsentation |

## Lizenz

Dieses Projekt ist ein studentisches Capstone und (noch) nicht lizenziert. Nutzung nur mit Genehmigung des Teams.

---

*Keine Anlageberatung. PRISMA ist ein Educational/Research-Tool.*
