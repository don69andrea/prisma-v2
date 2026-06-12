# PRISMA V2
### Quantitative Stock Intelligence Platform — Swiss Edition

> PRISMA zerlegt Aktien wie ein optisches Prisma weisses Licht — in analytische Dimensionen.  
> V2 bringt den Schweizer Markt, echtes ML und Entscheidungsintelligenz.

[![CI](https://github.com/don69andrea/prisma-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/don69andrea/prisma-v2/actions)
[![Issues](https://img.shields.io/github/issues/don69andrea/prisma-v2)](https://github.com/don69andrea/prisma-v2/issues)

---

## Was ist PRISMA V2?

PRISMA V2 ist eine quantitative Stock-Intelligence-Plattform für den Schweizer Markt (SMI/SMIM/SPI), entwickelt im BI-Modul FS 2026 (FHNW) von Andrea, Helin und Aurelius.

Das System kombiniert quantitative Finanzmodelle, Machine Learning und KI-Narrative zu einem einzigen Entscheidungssystem: **BUY / HOLD / WATCH** — jede Entscheidung begründet, auditierbar, erklärbar.

Zwei Anwendungsfälle:
- **FHNW BI Module:** Decision Intelligence mit ML, Portfolio Agent, Macro Agent
- **VIAC Stocks Initiative:** Infrastruktur für Einzeltitelhandel in der 3. Säule (3a)

---

## Status

| Bereich | Status |
|---------|--------|
| Swiss Market Universe (SMI/SMIM) | ✅ Live |
| Quant Scoring Engine (5 Modelle, SMI-kalibriert) | ✅ Live |
| BUY/HOLD/WATCH Signal-Dashboard | ✅ Live |
| Narrative Engine (Claude Sonnet, Pydantic) | ✅ Live |
| Multi-Agent Deep-Dive (Fundamentals + Sentiment + Synthesizer) | ✅ Live |
| Discovery Engine (5-Schritt Conversational Onboarding) | ✅ Live |
| Portfolio Intelligence Agent (Rebalancing, Mean-Variance) | ✅ Live |
| Macro Intelligence Agent (SNB/CHF/Inflation) | ✅ Live |
| ML Return Predictor (LightGBM, 19 Features) | ✅ Live — 61.4% Top-Quartil-Recall |
| 3a Eligibility Filter (FINMA-regelbasiert) | ✅ Live |
| Backtest Engine (vs. SMI Benchmark) | ✅ Live |
| MCP-Server (Claude Desktop Integration) | ✅ Live |
| Decision Audit Trail | ✅ Live |
| Demo-Flow + Präsentation | ⬜ In Arbeit |

---

## ML Return Predictor

Der LightGBM-Klassifikator ist das Herzstück des Entscheidungssystems. Er klassifiziert Aktien in drei Rendite-Klassen (Bottom / Mid / Top Quartil der 12-Monats-Vorwärtsrendite).

| Version | Trainingszeilen | Features | Top-Quartil-Recall |
|---------|----------------|----------|--------------------|
| v1 — CH-only, 3 Jahre | ~600 | 15 | 34.5% |
| v2 — CH+EU+US, 8 Jahre | 14'665 | 19 | 50.2% |
| **v3 — + SimFin Point-in-Time** | **14'665** | **19** | **61.4%** ✅ |

**Trainings-Universum:** 163 Ticker — 40 CH (SMI/SMIM) + 86 EU (DAX/CAC/FTSE/AEX/IBEX/MIB/OMX) + 45 US (S&P500 Mega-Caps)  
**Fundamentaldaten:** SimFin für US-Ticker (Point-in-Time korrekt via Publish Date), yfinance-Stub für CH/EU  
**Features:** 5 Quant-Scores + 12 technische Indikatoren (MACD, Bollinger Bands, Drawdown, Momentum) + 2 Makro-Features (Leitzins, FX)

→ Vollständige Dokumentation: [`docs/ml-training.md`](./docs/ml-training.md)  
→ Architektur-Entscheide: [`docs/adr/0008-ml-training-data-strategy.md`](./docs/adr/0008-ml-training-data-strategy.md)

---

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 14)                    │
│  /start (Discovery) · /decisions · /rankings · /backtest     │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────┐
│                     BACKEND (FastAPI)                        │
│                                                              │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────┐  │
│  │    DOMAIN    │  │   APPLICATION     │  │  INTERFACES  │  │
│  │  Entities    │  │  Services         │  │  REST + MCP  │  │
│  │  Value Obj.  │  │  Agents           │  │              │  │
│  │  Ports (ABC) │  │  ML Feature Svc   │  │              │  │
│  └──────────────┘  └─────────┬─────────┘  └──────────────┘  │
│                              │                               │
│  ┌───────────────────────────▼─────────────────────────────┐ │
│  │                   INFRASTRUCTURE                         │ │
│  │  PostgreSQL 16 · pgvector · yfinance (.SW)              │ │
│  │  Claude API (Sonnet/Haiku) · SimFin (Training)          │ │
│  │  LightGBM/XGBoost Modell · SNB/ECB/Fed Makrodaten       │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Clean Architecture — Dependency-Rule: innere Schichten kennen äussere nicht.

```
backend/
├── domain/           # Entities, Value Objects, Domain-Rules, Ports (ABC)
├── application/      # Services, Use Cases, Agents
├── interfaces/       # REST-Router, MCP-Server, Pydantic-Schemas
└── infrastructure/   # PostgreSQL-, Market-Data-, SimFin-Adapter, LLM-Client

scripts/              # Seed-Skripte (idempotent), ML-Training
docs/
├── ml-training.md    # ML-Pipeline: Features, Universum, SimFin, Ergebnisse
├── adr/              # Architecture Decision Records (0001–0008)
├── specs/            # Spec-First: ein .md pro Feature
└── superpowers/plans # Implementationspläne
```

---

## AI-Layer

| Layer | Technologie | Funktion |
|-------|-------------|---------|
| **Narrative Engine** | Claude Sonnet + Tool-Use + Pydantic | Research-Memos: One-Liner, Stärken, Risiken — validiert, kein Freitext |
| **Multi-Agent Deep-Dive** | Fundamentals + Sentiment + Synthesizer | Parallelisierte Dossiers für Top-N Picks |
| **Discovery Engine** | Claude Haiku + Session-State | 5-Schritt Onboarding: Beruf → Ziel → Risiko → Brands → Investor-Profil |
| **Portfolio Intelligence** | Claude Sonnet + Markowitz/Risk-Parity | Portfolio-Optimierung + Rebalancing-Plan |
| **Macro Intelligence** | Claude Sonnet + SNB RAG | CHF/SNB/Inflation-Kontext für alle Rankings |
| **Signal-Erklärung** | Claude Sonnet | WHY hinter jedem BUY/HOLD/WATCH — Quant + ML + Makro erklärt |
| **MCP-Server** | FastMCP | PRISMA aus Claude Desktop per Natursprache nutzbar |
| **ML Predictor** | LightGBM / XGBoost | Forward-Return-Klassen, 19 Features, 61.4% Top-Quartil-Recall |

---

## Stack

| Kategorie | Technologien |
|-----------|-------------|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic |
| **Datenbank** | PostgreSQL 16 · pgvector |
| **AI / LLM** | Claude API (Sonnet/Haiku) · MCP SDK (FastMCP) |
| **ML** | LightGBM · XGBoost · scikit-learn · pandas · SimFin (Training) |
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS · Recharts |
| **Testing** | pytest (704 Unit-Tests) · Playwright · Vitest |
| **DevOps** | GitHub Actions · Render (Free Tier, 512 MB RAM) |
| **Datenquellen** | yfinance (SIX `.SW`) · SNB/ECB/Fed Makrodaten · SimFin (US Fundamentals) |

---

## Modell-Routing

| Aufgabe | Modell | Warum |
|---------|--------|-------|
| Research-Memos, Signal-Erklärungen | `claude-sonnet-4-6` | Balance Qualität + Speed |
| Discovery-Klassifikation, Haiku-Responses | `claude-haiku-4-5-20251001` | Schnell + günstig für kurze Tasks |
| Forward-Return-Prediction | LightGBM / XGBoost | Deterministisch, erklärbar, auditierbar |

---

## Lokales Setup

**Voraussetzungen:** Docker, Python 3.12+, Node 20+

```bash
# Repo klonen
git clone https://github.com/don69andrea/prisma-v2.git
cd prisma-v2

# Environment vorbereiten
cp .env.example .env
# .env anpassen: ANTHROPIC_API_KEY, DATABASE_URL

# PostgreSQL starten
docker compose up -d

# Backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.interfaces.rest.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Tests

```bash
pytest backend/tests/unit -q          # 704 Unit-Tests (~3s)
pytest backend/tests/integration -q   # braucht laufende DB
```

### ML-Modell neu trainieren

```bash
# Standard (nur CH, ~5 Minuten)
python scripts/train_return_predictor.py

# Volles Universum mit SimFin Point-in-Time Fundamentaldaten (~25 Minuten)
python scripts/train_return_predictor.py --market all --years 8 \
    --simfin-key <KEY>   # kostenloser Key: simfin.com
```

→ Vollständige Trainings-Anleitung: [`docs/ml-training.md`](./docs/ml-training.md)

---

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [`docs/ml-training.md`](./docs/ml-training.md) | ML-Pipeline: Features, Universum, SimFin, Walk-Forward, Ergebnisse |
| [`docs/adr/`](./docs/adr/) | Architecture Decision Records (8 ADRs) |
| [`CLAUDE.md`](./CLAUDE.md) | Kontext für Claude Code — Status, Tasks, Swiss Market Regeln |
| [`AGENTS.md`](./AGENTS.md) | Coding-Konventionen (Python, TypeScript, Tests, Async-Patterns) |
| [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) | KI-Einsatz im Projekt (Transparenz) |

---

> **Disclaimer:** PRISMA V2 ist ein Bildungs- und Forschungsprojekt (FHNW BI Module FS 2026). Keine der hier generierten Analysen, Rankings, Scores oder Signale stellt eine Anlageberatung dar. Historische Performance ist kein Indikator für zukünftige Ergebnisse. Investitionsentscheide liegen ausschliesslich beim Anleger.

---

*PRISMA V2 · FHNW BI Module FS 2026 · Andrea Petretta, Helin, Aurelius · [don69andrea/prisma-v2](https://github.com/don69andrea/prisma-v2)*
