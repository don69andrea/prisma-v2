# PRISMA V2
### Quantitative Stock Intelligence Platform — Swiss Edition

> PRISMA zerlegt Aktien wie ein optisches Prisma weisses Licht — in analytische Dimensionen.  
> V2 bringt den Schweizer Markt, echtes ML und Entscheidungsintelligenz.

[![CI](https://github.com/don69andrea/prisma-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/don69andrea/prisma-v2/actions)
[![Issues](https://img.shields.io/github/issues/don69andrea/prisma-v2)](https://github.com/don69andrea/prisma-v2/issues)

---

## Was ist PRISMA V2?

PRISMA V2 ist eine quantitative Stock-Intelligence-Plattform für den Schweizer Markt (SMI/SMIM/SPI), entwickelt im BI-Modul FS 2026 (FHNW) von Andrea Petretta, Helin und Aurelius.

Das System kombiniert quantitative Finanzmodelle, Machine Learning und KI-Narrative zu einem einzigen Entscheidungssystem: **BUY / HOLD / SELL** — jede Entscheidung begründet, auditierbar, erklärbar.

Zwei Anwendungsfälle:

**ZIEL 1 — FHNW BI Module:** Den BI-Layer bauen — echtes ML (LightGBM/XGBoost Return Prediction), Agentic AI (Discovery + Portfolio + Macro + Steuer), RAG (pgvector + Voyage AI), Decision Intelligence Dashboard (BUY/HOLD/SELL). Jede Entscheidung ist begründet, auditierbar, erklärbar.

**ZIEL 2 — VIAC Stocks Initiative:** PRISMA V2 als potentielle Infrastruktur für VIAC Stocks (Einzeltitelhandel im **freien Vermögen**). Dafür: Swiss Market Universe (SMI/SMIM/SPI), Langfrist-Score, Steuer-Implikations-Agent, Fonds vs. Einzeltitel Vergleich. Zusätzlich: 3a Eligibility Filter (FINMA-regelbasiert) — zeigt welche SMI-Titel für die gebundene Vorsorge zugelassen wären.

---

## Was kann PRISMA V2?

PRISMA V2 ist dein persönlicher KI-Analyst für Schweizer Aktien — vollständig erklärbar, kein Black Box.

| Was du willst | Was PRISMA macht |
|---|---|
| **Welche Aktien soll ich kaufen?** | BUY / HOLD / SELL Signale für alle SMI/SMIM-Titel — mit KI-Begründung, nicht nur eine Zahl |
| **Welche Aktien passen zu mir?** | 5-Schritt Onboarding: Beruf, Ziel, Risikobereitschaft, Lieblingsmarken → persönliches Investor-Profil + Empfehlungen |
| **Was steckt hinter dieser Aktie?** | KI-Dossier pro Titel: Stärken, Risiken, Analyst-One-Liner, Modell-Konsistenz |
| **Was soll ich mit meinem Portfolio tun?** | Portfolio eingeben → Agent empfiehlt kaufen/halten/verkaufen (Markowitz oder Risk-Parity) |
| **Wie beeinflusst SNB/CHF/Inflation mein Portfolio?** | Makro-Agent: SNB-Entscheide, CHF/EUR, Inflation — kontextualisiert alle Rankings |
| **VIAC-Fonds oder Einzeltitel?** | Direkter Vergleich: Expected Return, Volatility, Sharpe, Max Drawdown |
| **Welche Titel darf ich für die 3. Säule kaufen?** | 3a Eligibility Filter — FINMA-regelbasiert, binär, auditierbar |
| **Wie hat sich meine Strategie historisch geschlagen?** | Backtest vs. SMI Benchmark: Sharpe, Max Drawdown, annualisierte Rendite |

Alle Entscheidungen inkl. vollständigem **Audit Trail** — nachvollziehbar, reproduzierbar, erklärbar.

---

## Status

| Bereich | Status |
|---------|--------|
| Swiss Market Universe (SMI/SMIM) | ✅ Live |
| Quant Scoring Engine (5 Modelle, SMI-kalibriert) | ✅ Live |
| BUY/HOLD/SELL Signal-Dashboard | ✅ Live |
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

## Lokales Setup

**Voraussetzungen:** Docker, Python 3.12+, Node 20+

```bash
# Repo klonen
git clone https://github.com/don69andrea/prisma-v2.git
cd prisma-v2

# Environment vorbereiten
cp .env.example .env
# .env anpassen: ANTHROPIC_API_KEY, DATABASE_URL, VOYAGE_API_KEY

# PostgreSQL starten
docker compose up -d

# Backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.interfaces.rest.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Demo-Daten seeden

```bash
# Swiss Stocks: SMI-20
python scripts/seed_smi_universe.py

# US-Stocks: Tech-Big-12 (empfohlen für reichhaltige Demo)
python scripts/seed_tech_catalog.py
```

Alle Seed-Skripte sind idempotent (`ON CONFLICT DO NOTHING`).

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
| [`docs/specs/`](./docs/specs/) | Spec-First: ein .md pro Feature vor erstem Commit |
| [`docs/AI-USAGE.md`](./docs/AI-USAGE.md) | KI-Einsatz im Projekt — Transparenz, Lektionen, Reflexionen |
| [`CLAUDE.md`](./CLAUDE.md) | Kontext für Claude Code — Status, Tasks, Swiss Market Regeln |
| [`AGENTS.md`](./AGENTS.md) | Coding-Konventionen (Python, TypeScript, Tests, Async-Patterns) |

---

<details open>
<summary><strong>Deep Dive — Architektur, Features, AI-Layer, Tech-Stack</strong></summary>

---

## Features

### BI-Layer (FHNW)

| | |
|---|---|
| **ML Return Prediction** | **Portfolio Intelligence Agent** |
| LightGBM/XGBoost auf Quant-Faktoren trainiert. Prediziert Forward-Returns in drei Klassen — echtes ML statt nur Ranking. Walk-Forward-Validation, kein Look-Ahead-Bias. 61.4% Top-Quartil-Recall. | 5. Agent: Kennt dein aktuelles Portfolio. Empfiehlt was du hinzufügen/entfernen sollst — nicht nur abstrakte Rankings. Mean-Variance oder Risk-Parity Optimierung. |
| `ML` | `Agent` |

| | |
|---|---|
| **Macro Intelligence Agent** | **Decision Intelligence Dashboard** |
| Monitort SNB-Entscheide, CHF/EUR, Inflation CH. Kontextualisiert alle Rankings mit makroökonomischen Signalen. | BUY / HOLD / SELL Signale mit KI-Begründung, Konfidenz-Balken und vollständigem Audit Trail. Quant 45% + ML 35% + Makro 20%. |
| `Agent` · `RAG` | `Dashboard` |

| | |
|---|---|
| **Discovery Engine** | **Narrative Engine** |
| 5-Schritt Conversational Onboarding: Beruf → Ziel → Risiko-Test → Schweizer Brands → Profil-Reveal. Claude Haiku + Session-State. | Claude Sonnet + Tool-Use + Pydantic. Strukturierte Research-Memos: Stärken, Risiken, Modell-Widersprüche, Analyst-One-Liner — kein Freitext. |
| `AI` · `Agent` | `AI` |

### Swiss / VIAC Layer

| | |
|---|---|
| **Swiss Market Universe** | **3a Eligibility Filter** |
| SMI (20), SMIM (30), SPI (200+) als primäres Universum. SIX Exchange Daten via yfinance (`.SW`-Suffix), CHF-denominiert, CH-ISIN mit Luhn-Mod-10 validiert. | FINMA-regelbasiert (kein LLM). Welche Titel wären für die gebundene Vorsorge zugelassen? Binär, transparent, auditierbar. Kriterien: Domizil, Anlageklasse, Liquidität (ADV), kein Hebel. |
| `Swiss` | `VIAC` |

| | |
|---|---|
| **Swiss RAG** | **Steuer-Implikations-Agent** |
| SIX Exchange Filings + NZZ/SRF News auf Deutsch. Voyage AI Embeddings (multilingual). Schweizer Kontext für jeden SMI/SMIM-Titel. | RAG über ESTV-Merkblätter + BVV2. Erklärt Verrechnungssteuer, Wertschriftverzeichnis, Rückforderung. Immer mit Disclaimer: *"Keine Steuerberatung."* |
| `RAG` · `Swiss` | `Agent` · `RAG` · `VIAC` |

| | |
|---|---|
| **Langfrist-Score** | **Fonds vs. Einzeltitel** |
| Score 0–10 für den 30-Jahres-Horizont: Dividendenstabilität, Bilanzqualität, ESG-Trend, Schweizer Verwurzelung. Sichtbar im Factsheet neben den 5 Quant-Modell-Cards. | VIAC-Strategiefonds (z.B. VIAC Global 100) vs. selbst zusammengestelltes Einzeltitel-Portfolio. Metrics: Expected Return, Volatility, Sharpe, Max Drawdown. |
| `VIAC` · `ML` | `VIAC` · `Dashboard` |

| | |
|---|---|
| **Multi-Agent Deep-Dive** | **MCP-Server** |
| Fundamentals-Agent + Sentiment-Agent + Synthesizer-Agent — parallelisierte Dossiers für Top-N Picks. | PRISMA direkt aus Claude Desktop per Natursprache nutzbar: *"Zeig mir Top-20% Quality + Trend Titel"* |
| `Agent` | `MCP` |

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
├── specs/            # Spec-First: ein .md pro Feature vor erstem Commit
└── superpowers/plans # Implementationspläne (Plan-as-Contract)
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
| **Steuer-Agent** | Claude Haiku + ESTV RAG | CH-Steuerimplikationen für freies Vermögen — immer mit Disclaimer |
| **Signal-Erklärung** | Claude Sonnet | WHY hinter jedem BUY/HOLD/SELL — Quant + ML + Makro erklärt |
| **MCP-Server** | FastMCP | PRISMA aus Claude Desktop per Natursprache nutzbar |
| **ML Predictor** | LightGBM / XGBoost | Forward-Return-Klassen, 19 Features, 61.4% Top-Quartil-Recall |

---

## Stack

| Kategorie | Technologien |
|-----------|-------------|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic |
| **Datenbank** | PostgreSQL 16 · pgvector |
| **AI / LLM** | Claude API (Sonnet/Haiku) · MCP SDK (FastMCP) · Voyage AI |
| **ML** | LightGBM · XGBoost · scikit-learn · pandas · SimFin (Training) |
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS · Recharts |
| **Testing** | pytest (704 Unit-Tests) · Playwright · Vitest |
| **DevOps** | GitHub Actions · Render (Free Tier, 512 MB RAM) |
| **Datenquellen** | yfinance (SIX `.SW`) · SNB/ECB/Fed Makrodaten · SimFin (US Fundamentals) |

---

## Modell-Routing

| Aufgabe | Modell | Warum |
|---------|--------|-------|
| Architektur, VIAC-Strategie, Trade-offs | Claude Opus | Urteilskraft > Schreibgeschwindigkeit |
| Research-Memos, Signal-Erklärungen | `claude-sonnet-4-6` | Balance Qualität + Speed |
| Discovery-Klassifikation, Haiku-Responses | `claude-haiku-4-5-20251001` | Schnell + günstig für kurze Tasks |
| Forward-Return-Prediction | LightGBM / XGBoost | Deterministisch, erklärbar, auditierbar |

---

## Entwicklungs-Workflow

```
Brainstorming → Spec-First → Plan-as-Contract → Subagent-Driven Execution → Two-Stage Review → Reflexion
```

1. **Brainstorming** — Architekturentscheidungen mit dem Team durchspielen, eine Frage pro Turn
2. **Spec-First** — Jedes Feature startet mit `docs/specs/YYYY-MM-DD-*.md`. Kein Code ohne freigegebene Spec
3. **Plan-as-Contract** — Detaillierte Implementationspläne als verbindlicher Vertrag
4. **Subagent-Driven Execution** — Frischer Subagent pro Task, kein Kontext-Spill zwischen Tasks
5. **Two-Stage Review** — Spec-Compliance-Review + Code-Quality-Review als separate Subagents
6. **Reflexion** — Jeder PR mit AI-Beteiligung landet in `docs/AI-USAGE.md`

```
feature/andrea-*  ──┐
feature/helin-*   ──┼──► main  (via PR, CI grün, 1 Review)
feature/aurelius-* ─┘
```

---

</details>

> **Disclaimer:** PRISMA V2 ist ein Bildungs- und Forschungsprojekt (FHNW BI Module FS 2026). Keine der hier generierten Analysen, Rankings, Scores oder Signale stellt eine Anlageberatung dar. Historische Performance ist kein Indikator für zukünftige Ergebnisse. Investitionsentscheide liegen ausschliesslich beim Anleger.

> *Technische Basis: PRISMA V1 lieferte Clean Architecture, 5 Quant-Modelle, Narrative Engine und Multi-Agent-Pipeline. V2 baut darauf auf.*

---

*PRISMA V2 · FHNW BI Module FS 2026 · Andrea Petretta, Helin, Aurelius · [don69andrea/prisma-v2](https://github.com/don69andrea/prisma-v2)*
