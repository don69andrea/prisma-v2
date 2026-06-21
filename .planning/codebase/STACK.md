---
title: STACK
last_mapped_commit: docs-map-2026-06-21
date: 2026-06-21
---

# Tech Stack — PRISMA V2

## Languages & Runtime
- **Python 3.13** (requires ≥3.12 per `pyproject.toml`) — backend
- **TypeScript 5.4** — frontend
- **Node.js 25.9** (local dev); Next.js builds run in Docker
- **Docker** — both services containerised (`Dockerfile.backend`, `Dockerfile.frontend`)

## Backend Framework
- **FastAPI ≥0.110** — REST API, OpenAPI auto-docs
  - Entry: `backend/interfaces/rest/app.py`
  - Routers: `backend/interfaces/rest/routers/` (decisions, rankings, backtest, discovery, signals…)
- **Pydantic v2 / pydantic-settings v2** — all schemas + settings validation
  - Settings singleton: `backend/config.py` (`get_settings()`)
- **SQLAlchemy 2.0 async** + **asyncpg ≥0.29** — async ORM + PostgreSQL driver
- **Alembic ≥1.13** — migrations in `backend/alembic/versions/` (0001–0022+)
- **pgvector ≥0.3** — vector extension for RAG embeddings
- **APScheduler ≥3.10** — background cron jobs (news ingestion, alert worker)
- **uvicorn** — ASGI server

## Frontend Framework
- **Next.js 14.2** (App Router) — `frontend/app/`
- **React 18.3** + **React DOM**
- **TypeScript 5.4**
- **Tailwind CSS 3.4** + **tailwind-merge** + **class-variance-authority**
- **Radix UI** — `@radix-ui/react-dialog`, `react-popover`, `react-slot`
- **TanStack React Query v5** — data fetching / cache
- **Recharts 2.12** — charts (Equity curve, Monte Carlo fan chart, SHAP waterfall)
- **Lucide React** — icons

## ML / Data Stack
- **scikit-learn ≥1.4** — pipelines, feature engineering, walk-forward CV
- **LightGBM ≥4.3** — gradient boosting (Vol-Forecast, Meta-Label)
- **XGBoost ≥2.0** — return-prediction (V3; also in V4 backtest comparison)
- **SHAP ≥0.45** — explainability (`backend/application/services/ml_prediction_service.py`)
- **pandas ≥2.2** + **numpy ≥1.26** — data wrangling
- **scipy ≥1.13** — Monte Carlo, stats
- **joblib ≥1.3** — model serialisation (`models/` directory)
- **yfinance ≥0.2.40** — price data (`backend/infrastructure/adapters/yfinance_swiss.py`)
- **`ta` library** (to be added in V4-1) — technical indicator reference values for test validation

## Database
- **PostgreSQL 16** (Render free tier; pgvector extension enabled)
- **pgvector** — `vector(1024)` columns for Swiss RAG chunks + embeddings
- ORM models: `backend/infrastructure/persistence/models/`
- Repositories: `backend/infrastructure/persistence/repositories/`

## AI / LLM
- **Anthropic Claude** via `anthropic ≥0.25` SDK
  - `claude-haiku-4-5-20251001` — fast classification tasks
  - `claude-sonnet-4-6` — research synthesis, narrative generation
  - Prompt-caching enabled for repeated system prompts (`cache_control: ephemeral`)
- **VoyageAI ≥0.2** — `voyage-3` embeddings for RAG chunks
- **MCP Server** — `backend/interfaces/mcp/server.py` + `tools/` (thin wrapper over application services)
- **WeasyPrint ≥62.0** — PDF report generation

## Key Config Files
- `pyproject.toml` — Python deps, ruff, mypy, pytest, coverage (fail_under=80)
- `frontend/package.json` — Node deps
- `frontend/tsconfig.json` — TypeScript config
- `frontend/tailwind.config.ts` — Tailwind theme
- `frontend/vitest.config.ts` — Vitest unit test config
- `frontend/playwright.config.ts` — E2E config
- `render.yaml` — deployment (2 web services + 1 cron)
- `.pre-commit-config.yaml` — ruff==0.15.11 pinned
