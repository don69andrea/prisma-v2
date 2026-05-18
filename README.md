# PRISMA

> Quantitatives Stock-Selection-Tool mit LLM-gestützter Research-Narrative und MCP-Integration.

PRISMA zerlegt Aktien in analytische Dimensionen — wie ein optisches Prisma weisses Licht in sein Spektrum zerlegt. Fünf quantitative Modelle in vier Kategorien (Quality, Trend, Value, Risk) bewerten jedes Unternehmen eines gewählten Universums. Eine Claude-gestützte Narrative Engine erklärt die Rankings in Klartext, ein Multi-Agent-Research-Pipeline produziert Deep-Dive-Dossiers für Top-Aktien, und ein MCP-Server macht PRISMA direkt aus Claude Desktop nutzbar.

**Capstone-Projekt** im Modul *AI-assisted Software Development*, BSc Business Artificial Intelligence, FHNW Hochschule für Wirtschaft, FS 2026. Referenz: PRISMA der Vireos AG.

## Abgabe-Status

Sichtbare Nachweise gegen das Capstone-Bewertungsraster (Stand: 2026-05-17).

| Kriterium | Status | Nachweis |
|---|---|---|
| **Architektur** | Clean Architecture (4 Schichten: Domain / Application / Interfaces / Infrastructure) | [`docs/specs/2026-04-21-prisma-capstone-design.md`](./docs/specs/2026-04-21-prisma-capstone-design.md) · siehe Architektur-Sektion unten |
| **Tests** | Backend Unit + Integration · Frontend Vitest · Playwright E2E | [`backend/tests/`](./backend/tests) · [`frontend/app/**/__tests__/`](./frontend/app) · [`frontend/e2e/`](./frontend/e2e) |
| **Test-Coverage** | ~89.8% Backend lokal verifiziert | [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) — Coverage-Gate-Eintrag |
| **CI** | GitHub Actions: Backend Lint+Tests, Frontend Lint+Build, Frontend E2E (Playwright) | [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) · [Actions-Tab](https://github.com/SheylaSam/prisma-capstone/actions) |
| **Release-Workflow** | Tag `v*` → Docker-Images auf GHCR + GitHub Release mit Auto-Notes | [`.github/workflows/release.yml`](./.github/workflows/release.yml) |
| **CD-Workflow** | `workflow_dispatch` → Render Deploy Hook (Backend / Frontend / beide) | [`.github/workflows/cd-render.yml`](./.github/workflows/cd-render.yml) |
| **Deployment** | Live auf Render (Free-Plan) | Frontend: [prisma-frontend-jrto.onrender.com](https://prisma-frontend-jrto.onrender.com) · Backend: [prisma-backend-7ai7.onrender.com/health](https://prisma-backend-7ai7.onrender.com/health) · Config: [`render.yaml`](./render.yaml) |
| **API-Docs** | OpenAPI/Swagger automatisch generiert (FastAPI) | [prisma-backend-7ai7.onrender.com/docs](https://prisma-backend-7ai7.onrender.com/docs) |
| **AI-Usage-Log** | Reflexion pro PR mit Agent / Patterns / Lehren — 40%-Bewertungsachse | [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) (>15 Einträge, Pattern-Sektion mit Evidenz-Links) |

### Demo-Flow

End-to-End mit der ausgelieferten UI:

1. **Health-Check** — `/` zeigt API-Health-Badge (Backend-Connectivity).
2. **Neues Universum anlegen** — `/universes/new` → Name, Region, Ticker → Eintrag erscheint in `/universes`.
3. **Ranking starten** — `/rankings` → Universe wählen → "Run starten" (~5-60s je nach Universe-Grösse).
4. **Ergebnis lesen** — `/rankings/[runId]` zeigt 9-Spalten-Tabelle: Rank · Ticker · Avg · Sweet-Spot · 5 Modell-Ranks. Sweet-Spot-Aktien markiert per Badge.

Selber Flow läuft als Playwright-Test in CI (`frontend/e2e/rankings.spec.ts`, Tests 1-3).

> **Hinweis Free-Tier**: Der Render-Free-Plan schläft Services nach 15 min Inaktivität ein. Erster Request nach Pause kann 30-60s dauern (Cold-Start). Aggressive Browser-Adblocker (uBlock Origin, Brave Shields o.ä.) können Requests zu `*.onrender.com` blocken — Test in Inkognito empfohlen.

## Features

- **Quant Core**: 5 Modelle (Quality Classic, Alpha, Trend Momentum / EWMA, Value Alpha Potential, Diversification / Ledoit-Wolf)
- **Narrative Engine**: LLM-generierte, strukturierte Research-Memos (Claude API + Pydantic-Schema)
- **Multi-Agent Deep-Dive**: Fundamentals / Sentiment / Synthesizer-Agenten für Top-10
- **MCP-Server**: PRISMA als Tool aus Claude Desktop nutzbar
- **Backtest**: Benchmark-Vergleich mit Sharpe, MaxDD, annualisierter Rendite

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

# Backend-Dependencies + Migrations
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn interfaces.rest.app:app --reload

# Frontend
cd ../frontend
npm install
npm run dev
```

Ausführliche Setup-Anleitung + Troubleshooting: **[docs/getting-started.md](./docs/getting-started.md)**

## Demo-Daten

```bash
python scripts/seed_demo_universe.py   # legt "Demo-US-5" mit AAPL/MSFT/GOOGL/NVDA/JPM an
```

Idempotent — mehrfaches Ausführen erzeugt keine Duplikate.

## Testen

```bash
pytest                      # Unit + Integration
pytest --cov=backend        # mit Coverage-Report
npx playwright test         # E2E
```

## Dokumentation

- **Design-Spec**: [`docs/specs/2026-04-21-prisma-capstone-design.md`](./docs/specs/2026-04-21-prisma-capstone-design.md)
- **Architecture Decision Records**: [`docs/adr/`](./docs/adr)
- **Agent-Konventionen**: [`AGENTS.md`](./AGENTS.md)
- **Contribution-Guidelines**: [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **AI-Nutzungs-Reflexion**: [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) (wird laufend geführt)

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
