---
date: 2026-06-21
focus: arch
---

# PRISMA V2 — Directory Structure

## Top-Level Layout

```
prisma-v2/
├── backend/                  Python backend (FastAPI + SQLAlchemy)
├── frontend/                 Next.js 14 frontend
├── docs/                     Documentation, specs, research
├── scripts/                  One-off ingestion / seed scripts
├── pyproject.toml            Python deps + ruff/mypy/pytest/coverage config
├── render.yaml               Render.com deployment config
├── CLAUDE.md                 Agent coding rules (Spec-First, Pydantic, CI gate)
└── .planning/                GSD planning docs (map, phases, state)
```

## Backend (`backend/`)

```
backend/
├── domain/
│   ├── entities/             Core business objects (plain Python classes)
│   │   ├── alert.py
│   │   ├── backtest_result.py
│   │   ├── decision_audit_record.py
│   │   ├── document.py
│   │   ├── embedding_chunk.py
│   │   ├── investor_profile.py
│   │   ├── memo_batch_job.py
│   │   ├── news_article.py / news_chunk.py
│   │   ├── ranking_run.py
│   │   ├── research_memo.py
│   │   ├── stock.py / swiss_stock.py
│   │   └── universe.py
│   ├── value_objects/        Immutable typed data containers
│   │   ├── decision_signal.py       (BUY/HOLD/SELL signal + rationale)
│   │   ├── ml_feature_vector.py
│   │   ├── ml_prediction.py
│   │   ├── portfolio_allocation.py
│   │   ├── rebalancing_plan.py
│   │   ├── swiss_fundamentals.py
│   │   ├── swiss_quant_score.py
│   │   └── macro_context.py
│   ├── schemas/              Pydantic schemas for LLM output validation
│   └── services/             Pure domain logic (no I/O)
│       └── swiss_quant_scorer.py
│
├── application/
│   ├── agents/               LLM agents (Tool-Use + Pydantic output)
│   │   ├── macro_agent.py    (MacroAgentV2 — macroeconomic regime)
│   │   ├── portfolio_agent.py (Markowitz + delta rebalancing)
│   │   └── steuer_agent.py   (Gold-standard pattern: RAG+LLM+Fallback)
│   └── services/             Business use cases (orchestration)
│       ├── alert_service.py
│       ├── backtest_service.py
│       ├── chat_service.py
│       ├── decision_audit_service.py
│       ├── discovery_service.py
│       ├── factsheet_service.py
│       ├── macro_service.py
│       ├── ml_feature_service.py / ml_prediction_service.py
│       ├── monte_carlo_service.py
│       ├── narrative_service.py
│       ├── news_ingestion_service.py / news_retrieval_service.py
│       ├── ranking_aggregator.py / ranking_run_service.py
│       ├── report_service.py
│       ├── retrieval_service.py
│       ├── signal_aggregation_service.py  (existing SMI signal logic)
│       ├── signal_validation_service.py
│       ├── stock_service.py
│       ├── swiss_market_service.py
│       └── universe_service.py
│
├── infrastructure/
│   ├── adapters/             External API adapters
│   │   ├── notification_adapter.py
│   │   ├── pdf_parser.py
│   │   ├── rss_news_adapter.py
│   │   ├── simfin_adapter.py       (CH fundamentals, excluded from coverage)
│   │   ├── six_filings_adapter.py
│   │   ├── snb_adapter.py
│   │   ├── ticker_ner.py
│   │   └── yfinance_swiss.py       (price data, basis for crypto extension)
│   ├── llm/
│   │   ├── client.py               (Anthropic SDK wrapper)
│   │   └── prompts/prompt_loader.py
│   ├── persistence/
│   │   ├── models/                 SQLAlchemy ORM models (0001–0022 migrations)
│   │   └── repositories/          Async repository implementations
│   │       ├── alert_repository.py
│   │       ├── backtest_result_repository.py
│   │       ├── embedding_repository.py
│   │       ├── ranking_run_repository.py
│   │       ├── research_memo_repository.py
│   │       ├── stock_repository.py
│   │       └── ... (14 repositories total)
│   └── workers/
│       └── alert_worker.py         (APScheduler background tasks)
│
├── interfaces/
│   ├── rest/
│   │   ├── app.py                  FastAPI application factory
│   │   ├── routers/               25 route modules (admin, alerts, backtests,
│   │   │                          chat, decisions, discovery, stocks, ...)
│   │   └── schemas/               Pydantic request/response schemas (26 files)
│   └── mcp/
│       └── server.py              MCP tool server (external agent interface)
│
├── alembic/
│   └── versions/                  DB migrations 0001–0022
│       └── 0022_fix_swiss_rag_embedding_dim.py  ← latest
│
└── tests/
    ├── unit/application/          Fast unit tests (no DB)
    ├── unit/domain/
    ├── unit/infrastructure/
    └── integration/               Real DB tests (pytest-asyncio, aiosqlite→asyncpg)
```

## Frontend (`frontend/`)

```
frontend/
├── app/                      Next.js 14 App Router pages
│   ├── alerts/               Alert management UI
│   ├── backtest/             Backtest form + results
│   ├── dashboard/            Main dashboard (MacroWidget, StatsCards)
│   ├── decision/             BUY/HOLD/SELL decision view
│   ├── discover/             Stock discovery / screener
│   ├── fonds/                Fund comparison
│   ├── news/                 News feed + RAG search
│   ├── portfolio/            Portfolio overview + Monte Carlo
│   │   └── simulator/        Monte Carlo simulator client
│   ├── rankings/             Ranking runs list + detail
│   │   └── [runId]/stock/[ticker]/  Factsheet
│   ├── research/             Research memo viewer
│   ├── start/                Onboarding / start screen
│   ├── steuer/               Tax analysis (SteuerAgent frontend)
│   ├── stocks/               Stock list + [ticker] detail page
│   ├── universes/            Universe management + wizard
│   └── watchlist/            Watchlist (new in 2026-06-14 overhaul)
│
├── components/
│   ├── factsheet/            Factsheet-specific components
│   │   ├── AuditPanel.tsx
│   │   ├── SHAPWaterfallChart.tsx
│   │   └── MemoPanel.tsx
│   ├── portfolio/            Portfolio-specific components
│   ├── dashboard/            Dashboard widgets
│   ├── chat/                 ChatDrawer + ChatMessage
│   └── ui/                   Shared primitives
│       ├── SignalBadge.tsx   (BUY/HOLD/SELL badge)
│       ├── SignalBreakdown.tsx
│       ├── AuditTrail.tsx
│       ├── InfoTooltip.tsx
│       └── ModeToggle.tsx    (new: PRISMA mode toggle)
│
├── hooks/
│   └── usePrismaMode.ts      (new: controls SMI vs Krypto display mode)
│
├── lib/api/                  Typed fetch wrappers (one per resource)
│   ├── backtest.ts / audit.ts / chat.ts / decisions.ts
│   ├── discovery.ts / eligibility.ts / fundamentals.ts
│   └── stocks.ts / ...
│
├── e2e/                      Playwright E2E tests (13 spec files)
└── middleware.ts             Next.js middleware (auth/redirect)
```

## Docs (`docs/`)

```
docs/
├── AGENT_CONTEXT.md          Agent coding brief (referenced in CLAUDE.md)
├── AI-USAGE.md               AI usage log (updated per phase)
├── DEMO-SCRIPT.md
├── PRISMA_V35_MASTERPLAN.md  ← V4 Vision + PoC evidence (added 2026-06-21)
├── PRISMA_V4_PROJEKTPLAN.md  ← V4 overall plan (added 2026-06-21)
├── PRISMA_V4_AGENTS.md       ← V4 agent brief (added 2026-06-21)
├── PRISMA_V4-1_PHASENPLAN_Signal-Engine.md  ← V4-1 spec (added 2026-06-21)
├── research/                 PoC scripts + raw data (BTC/ETH CSV)
│   ├── poc_feasibility.py
│   ├── indicator_backtest.py
│   ├── poc_results.txt / indicator_results.txt
│   ├── BTC-USD.csv / ETH-USD.csv
├── specs/                    Feature specs
├── adr/                      Architecture Decision Records
└── pitch/                    Presentation materials
```

## Naming Conventions

**Python (backend):**
- Files: `snake_case.py`
- Classes: `PascalCase` (e.g. `SteuerAgent`, `RankingRun`)
- Functions/variables: `snake_case`
- Pydantic models in `backend/interfaces/rest/schemas/` and `backend/domain/schemas/`
- Services named `<noun>_service.py`, agents named `<noun>_agent.py`

**TypeScript (frontend):**
- Files: `camelCase.ts` for utils/lib, `PascalCase.tsx` for components
- Components: `PascalCase` (e.g. `SignalBadge`, `AuditPanel`)
- API clients: `camelCase` functions in `frontend/lib/api/<resource>.ts`
- Page files always named `page.tsx`, client files `<route>-client.tsx`

## Highest Migration Number

`0022_fix_swiss_rag_embedding_dim.py` — V4-1 will add migrations 0037–0039 (crypto_universe, crypto_onchain_history, market_sentiment).
