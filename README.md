# PRISMA

> Quantitatives Stock-Selection-Tool mit LLM-gestützter Research-Narrative und MCP-Integration.

PRISMA zerlegt Aktien in analytische Dimensionen — wie ein optisches Prisma weisses Licht in sein Spektrum zerlegt. Fünf quantitative Modelle in vier Kategorien (Quality, Trend, Value, Risk) bewerten jedes Unternehmen eines gewählten Universums. Eine Claude-gestützte Narrative Engine erklärt die Rankings in Klartext, ein Multi-Agent-Research-Pipeline produziert Deep-Dive-Dossiers für Top-Aktien, und ein MCP-Server macht PRISMA direkt aus Claude Desktop nutzbar.

**Capstone-Projekt** im Modul *AI-assisted Software Development*, BSc Business Artificial Intelligence, FHNW Hochschule für Wirtschaft, FS 2026. Referenz: PRISMA der Vireos AG.

## Features

- **Quant Core**: 5 Modelle (Quality Classic, Quality AI / Lasso, Alpha, Anti-Cyclical, Diversification / Ledoit-Wolf)
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

Ausführliche Setup-Anleitung + Troubleshooting in [`docs/getting-started.md`](./docs/getting-started.md) (folgt in Woche 2).

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
