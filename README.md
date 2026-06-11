# PRISMA V2
### Quantitative Stock Intelligence Platform — Swiss Edition

> PRISMA zerlegt Aktien wie ein optisches Prisma weisses Licht — in analytische Dimensionen.
> V2 bringt den Schweizer Markt, echtes ML und Entscheidungsintelligenz.

[![CI](https://github.com/don69andrea/prisma-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/don69andrea/prisma-v2/actions)
[![Issues](https://img.shields.io/github/issues/don69andrea/prisma-v2)](https://github.com/don69andrea/prisma-v2/issues)
[![Milestone v2.0](https://img.shields.io/badge/milestone-v2.0_Swiss_Foundation-blue)](https://github.com/don69andrea/prisma-v2/milestone/1)

---

## PRISMA V2 — Evolutionsplan

PRISMA V2 ist eine quantitative Stock-Intelligence-Plattform für den Schweizer Markt — entwickelt im Rahmen des BI-Moduls (FHNW FS 2026) als Gruppenarbeit von Andrea, Helin und Aurelius. Zwei Ziele:

**ZIEL 1 — FHNW BI Module (Gruppenarbeit):** Den BI-Layer auf PRISMA aufbauen — echtes ML (XGBoost Return Prediction), Portfolio Intelligence Agent (5. Agent), Macro Intelligence Agent (SNB/CHF), und ein Decision Intelligence Dashboard mit BUY/HOLD/WATCH Signalen. Jede Entscheidung ist begründet, auditierbar, erklärbar.

**ZIEL 2 — VIAC Stocks Initiative:** PRISMA V2 als potentielle Infrastruktur für VIAC Stocks (Einzeltitelhandel in der 3. Säule). Dafür: Swiss Market Universe (SMI/SPI/SMIM), 3a Eligibility Filter (FINMA-regelbasiert), Swiss RAG (SIX Exchange + NZZ/SRF auf Deutsch), Steuer-Implikations-Agent (ESTV RAG), Langfrist-Score (30-Jahres-Horizont), Fonds vs. Einzeltitel Vergleich.

---

## PRISMA V2 — WAS BEREITS EXISTIERT

| Komponente | Beschreibung |
|---|---|
| **Quant Core** | 5 Scoring-Modelle: Quality, Trend Momentum, Value, Diversification (Ledoit-Wolf) — SMI-kalibriert |
| **Narrative Engine** | Claude Sonnet + Tool-Use + Pydantic. Research-Memos: Stärken, Risiken, One-Liner |
| **Multi-Agent Pipeline** | Fundamentals-Agent + Sentiment-Agent + Synthesizer-Agent |
| **Discovery Engine** | 5-Schritt-Onboarding: Beruf → Ziel → Risiko-Feeling-Test → Brands → Profil-Reveal |
| **MCP-Server** | PRISMA aus Claude Desktop per Natursprache nutzbar |
| **Backtest** | Benchmark-Vergleich (SMI) mit Sharpe, MaxDrawdown, annualisierter Rendite |

---

## NEU IN V2 — BI-LAYER

| | |
|---|---|
| **ML Return Prediction** `NEU` | **Portfolio Intelligence Agent** `NEU` |
| XGBoost/LightGBM auf Quant-Faktoren trainiert. Prediziert Forward-Returns in drei Klassen — echtes ML statt nur Ranking. Walk-Forward-Validation, kein Look-Ahead-Bias. | 5. Agent: Kennt dein aktuelles Portfolio. Empfiehlt was du hinzufügen/entfernen sollst — nicht nur abstrakte Rankings. Mean-Variance oder Risk-Parity Optimierung. |
| `ML` · Issue [#12](../../issues/12), [#13](../../issues/13) | `Agent` · Issue [#15](../../issues/15), [#16](../../issues/16) |

| | |
|---|---|
| **Macro Intelligence Agent** `NEU` | **Decision Intelligence Dashboard** `NEU` |
| Monitort SNB-Entscheide, CHF/EUR, Inflation CH. Kontextualisiert alle Rankings mit makroökonomischen Signalen. | Nicht nur Rankings — BUY / HOLD / WATCH Signale mit KI-Begründung, Konfidenz-Balken und vollständigem Audit Trail. |
| `Agent` · `RAG` · Issue [#17](../../issues/17) | `Dashboard` · Issue [#18](../../issues/18), [#19](../../issues/19) |

---

## NEU IN V2 — SWISS / VIAC LAYER

| | |
|---|---|
| **Swiss Market Universe** `NEU` | **3a Eligibility Filter** `NEU` |
| SMI (20), SMIM (30), SPI (200+) als primäres Universum. SIX Exchange Daten via yfinance (`.SW`-Suffix), CHF-denominiert, CH-ISIN mit Luhn-Mod-10 validiert. ✅ Issue #1 shipped. | FINMA-regelbasiert (kein LLM). Welche Titel sind für die 3. Säule zugelassen? Binär, transparent, auditierbar. Kriterien: Domizil, Anlageklasse, Liquidität (ADV), kein Hebel. |
| `Swiss` · Issue [#1](../../issues/3) ✅ | `VIAC` · Issue [#8](../../issues/10) |

| | |
|---|---|
| **Swiss RAG** `NEU` | **Steuer-Implikations-Agent** `NEU` |
| SIX Exchange Filings + NZZ/SRF News auf Deutsch. Voyage AI Embeddings (multilingual). Schweizer Kontext für jeden SMI/SMIM-Titel. | RAG über ESTV-Merkblätter + BVV2. Erklärt Verrechnungssteuer, Wertschriftverzeichnis, Rückforderung. Immer mit Disclaimer: *"Keine Steuerberatung."* |
| `RAG` · `Swiss` · Issue [#5](../../issues/7), [#6](../../issues/8) | `Agent` · `RAG` · `VIAC` · Issue [#7](../../issues/9) |

| | |
|---|---|
| **Langfrist-Score** `NEU` | **Fonds vs. Einzeltitel** `NEU` |
| Score 0–10 für den 30-Jahres-Horizont: Dividendenstabilität, Bilanzqualität, ESG-Trend, Schweizer Verwurzelung. Sichtbar im Factsheet neben den 5 Quant-Modell-Cards. | VIAC-Strategiefonds (z.B. VIAC Global 100) vs. selbst zusammengestelltes Einzeltitel-Portfolio. Metrics: Expected Return, Volatility, Sharpe, Max Drawdown. |
| `VIAC` · `ML` · Issue [#9](../../issues/11) | `VIAC` · `Dashboard` · Issue [#21](../../issues/21) |

---

## ARCHITEKTUR

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 14)             │
│  Dashboard · Ranking · Factsheet · Decision · Alert  │
└─────────────────────┬───────────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────────┐
│                BACKEND (FastAPI)                     │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │   DOMAIN    │  │  APPLICATION │  │ INTERFACES │  │
│  │  Entities   │  │  Services /  │  │ REST + MCP │  │
│  │  Rules      │  │  Use Cases   │  │            │  │
│  └─────────────┘  └──────┬───────┘  └────────────┘  │
│                          │                           │
│  ┌───────────────────────▼───────────────────────┐  │
│  │              INFRASTRUCTURE                    │  │
│  │  PostgreSQL 16  ·  pgvector  ·  Redis Cache   │  │
│  │  Claude API  ·  SIX Exchange  ·  SNB Data     │  │
│  │  XGBoost Models  ·  Voyage AI Embeddings      │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Clean Architecture mit vier Schichten — Dependency-Rule: innere Schichten kennen äussere nicht.

```
backend/
├── domain/           # Entities, Value Objects, Domain-Rules, Ports (ABC)
├── application/      # Services, Use Cases, Agents
├── interfaces/       # REST-Router, MCP-Server, Pydantic-Schemas
└── infrastructure/   # PostgreSQL-Adapter, Market-Data-Adapter, LLM-Client

scripts/              # Seed-Skripte (idempotent), Training-Skripte
docs/
├── specs/            # Spec-First: ein .md pro Feature vor erstem Commit
├── superpowers/plans # Implementationspläne (Plan-as-Contract)
└── adr/              # Architecture Decision Records
```

---

## AI-LAYER IM PRODUKT

| Layer | Technologie | Funktion |
|---|---|---|
| **1 · Narrative Engine** | Claude Sonnet + Tool-Use + Pydantic | Research-Memos: One-Liner, Stärken, Risiken, Modell-Widersprüche — Pydantic-validiert, kein Freitext |
| **2 · Multi-Agent Deep-Dive** | Fundamentals + Sentiment + Synthesizer | Parallelisierte Dossiers für Top-N Picks |
| **3 · Portfolio Intelligence** | Claude Sonnet + Markowitz/Risk-Parity | Portfolio-Optimierung + Rebalancing-Plan |
| **4 · Macro Intelligence** | Claude Sonnet + SNB RAG | CHF/SNB-Kontext für alle Rankings |
| **5 · Steuer-Agent** | Claude Haiku + ESTV RAG | CH-Steuerimplikationen für 3a — immer mit Disclaimer |
| **6 · MCP-Server** | MCP SDK (FastMCP) | PRISMA aus Claude Desktop per Natursprache nutzbar |
| **7 · ML Predictor** | XGBoost / LightGBM | Forward-Return-Klassen (Top/Mitte/Bottom-Quartil) |

---

## STACK

| Kategorie | Technologien |
|---|---|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic |
| **Datenbank** | PostgreSQL 16 · pgvector · Redis |
| **AI / LLM** | Claude API (Opus/Sonnet/Haiku) · MCP SDK · Voyage AI |
| **ML** | XGBoost · LightGBM · scikit-learn · pandas |
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS · Recharts |
| **Testing** | pytest · Playwright · Vitest (Coverage ≥ 80%) |
| **DevOps** | Docker · GitHub Actions · Render · GHCR |
| **Datenquellen** | SIX Exchange · Yahoo Finance (`.SW`) · SNB API · ESTV |

---

## ROADMAP

```
v2.0 — Swiss Foundation                                 FS 2026
├── ✅ Swiss Market Universe (SMI/SMIM/SPI)             Issue #1 shipped
├──    Swiss Market Data Adapter (yfinance live)        Issue #3
├──    Quant Models — Swiss Kalibrierung (SMI Benchmark) Issue #4
├──    Swiss RAG (SIX Filings + NZZ/SRF)               Issue #5, #6
├──    3a Eligibility Filter (FINMA-regelbasiert)       Issue #8
├──    Steuer-Implikations-Agent (ESTV RAG)             Issue #7
└──    Render V2 Deployment Setup                       Issue #23

v2.1 — ML Intelligence Layer
├──    ML Feature Engineering (Quant Scores → XGBoost) Issue #10
├──    XGBoost Return Predictor — Training + Evaluation Issue #11
├──    ML Prediction API Endpunkt                       Issue #12
├──    Portfolio Intelligence Agent (5. Agent)          Issue #13, #14
└──    Macro Intelligence Agent (SNB/CHF)               Issue #15

v2.2 — Decision Intelligence + VIAC Pitch-Ready
├──    BUY / HOLD / WATCH Dashboard                     Issue #16
├──    Decision Audit Trail (Erklärbarkeit)             Issue #17
├──    Alert Engine (Price + Signal Alerts)             Issue #18
├──    Langfrist-Score (30-Jahres-Horizont)             Issue #9
├──    Fonds vs. Einzeltitel Vergleich                  Issue #19
└──    VIAC Pitch Deck                                  Issue #20
```

---

## SETUP

Voraussetzungen: Docker, Docker Compose, Python 3.12+, Node 20+.

```bash
# Repo klonen
git clone https://github.com/don69andrea/prisma-v2.git
cd prisma-v2

# Environment vorbereiten
cp .env.example .env
# .env anpassen: ANTHROPIC_API_KEY, DATABASE_URL, VOYAGE_API_KEY

# Services starten (PostgreSQL + pgvector)
docker compose up -d

# Backend-Dependencies + Migrations
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.interfaces.rest.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Demo-Daten seeden

```bash
# US-Stocks: Demo-Universe (5 Tickers: AAPL/MSFT/GOOGL/NVDA/JPM)
python scripts/seed_demo_universe.py

# US-Stocks: Tech-Big-12 (empfohlen für reichhaltige Demo)
python scripts/seed_tech_catalog.py

# Swiss Stocks: SMI-20 Seed (Issue #1) — nach ISIN-Verifikation
python scripts/seed_smi_universe.py
```

Alle Seed-Skripte sind idempotent (`ON CONFLICT DO UPDATE`).

### RAG-Ingestion (einmalig)

```bash
# US-Filings (SEC EDGAR 10-K/10-Q → pgvector)
python scripts/ingest_filings.py

# Swiss-Filings (SIX Exchange → pgvector) — ab Issue #5
python scripts/ingest_swiss_filings.py
```

### Tests

```bash
pytest                      # Unit + Integration
pytest --cov=backend        # mit Coverage-Report
npx playwright test         # E2E (Frontend)
```

---

## ENTWICKLUNGS-WORKFLOW

```
feature/andrea-* ──┐
feature/helin-*  ──┼──► develop ──► main
feature/aurelius-* ─┘
```

Jede Person arbeitet auf ihrem Feature-Branch. PRs gehen nach `develop`, kein direkter Push auf `main`. Commit-Format: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).

Der Coding-Konventions-Vertrag für alle Agents: [`AGENTS.md`](./AGENTS.md)

---

## MODELL-ROUTING

| Aufgabe | Modell | Warum |
|---|---|---|
| Architektur, VIAC-Strategie, Trade-offs | Claude Opus | Urteilskraft > Schreibgeschwindigkeit |
| Features, Agents, RAG, Reviews | Claude Sonnet | Balance Qualität + Speed |
| Klassifikation, Strukturierung, Haiku-Responses | Claude Haiku | Schnell + günstig für Triviales |
| Forward-Return-Prediction | XGBoost / LightGBM | Deterministisch, erklärbar, auditierbar |

---

## DOKUMENTATION

| Dokument | Inhalt |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Kontext für Claude Code Agents — Status, Tasks, Swiss Market Regeln |
| [`AGENTS.md`](./AGENTS.md) | Technische Coding-Konventionen (Python, TypeScript, Tests) |

---

---

> **Disclaimer:** PRISMA V2 ist ein Bildungs- und Forschungsprojekt. Keine der hier generierten Analysen, Rankings, Scores oder Signale stellt eine Anlageberatung dar. Historische Performance ist kein Indikator für zukünftige Ergebnisse. Investitionsentscheide liegen ausschliesslich beim Anleger.

---

*PRISMA V2 · FHNW BI Module FS 2026 · [don69andrea/prisma-v2](https://github.com/don69andrea/prisma-v2) · VIAC Stocks Initiative*
