---
title: INTEGRATIONS
last_mapped_commit: docs-map-2026-06-21
date: 2026-06-21
---

# External Integrations — PRISMA V2

## Anthropic Claude API
- **SDK**: `anthropic ≥0.25` (Python)
- **Key**: `ANTHROPIC_API_KEY` env var (required in production)
- **Models in use**:
  - `claude-haiku-4-5-20251001` — fast classification, discovery agent
  - `claude-sonnet-4-6` — research synthesis, SteuerAgent, MacroAgent
- **Usage pattern**: async calls with Pydantic-validated outputs; prompt-caching via `cache_control: ephemeral`
- **Relevant files**:
  - `backend/application/agents/steuer_agent.py`
  - `backend/application/agents/macro_agent.py`
  - `backend/application/agents/portfolio_agent.py`
  - `backend/application/services/narrative_service.py`
  - `backend/application/services/chat_service.py`
- **Budget cap**: $20 USD configurable via `BUDGET_CAP_USD` env; tracked in `cost_tracker.py`

## VoyageAI (Embeddings)
- **SDK**: `voyageai ≥0.2`
- **Key**: `VOYAGE_API_KEY` env var
- **Model**: `voyage-3` — 1024-dim vectors
- **Use**: Swiss RAG chunk embeddings, stored in `swiss_rag_chunks` table (pgvector)
- **Relevant files**:
  - `backend/application/services/retrieval_service.py`
  - `backend/infrastructure/persistence/models/` (vector columns)

## yfinance (Market Data — Swiss)
- **Library**: `yfinance ≥0.2.40`
- **Use**: OHLCV + `.info` for SMI/SMIM/SPI tickers (`.SW` suffix format: `NESN.SW`)
- **Constraint**: `.info` dict returns `None` for ISIN on Swiss tickers — manual ISIN lookup required
- **Async pattern**: `asyncio.to_thread()` (NOT `run_in_executor`)
- **Relevant files**:
  - `backend/infrastructure/adapters/yfinance_swiss.py` — `YFinanceSwissAdapter`
  - `backend/application/services/stock_service.py`
- **V4-1 addition**: yfinance also used for BTC/ETH/Top-10 crypto OHLCV (daily, `BTC-USD` format)

## SIX Exchange (Swiss Filings)
- **Adapter**: `backend/infrastructure/adapters/six_filings_adapter.py`
- **Use**: Swiss corporate filings, PDFs → RAG corpus
- **Script**: `scripts/ingest_swiss_filings.py`

## SimFin (Fundamentals)
- **Adapter**: `backend/infrastructure/adapters/simfin_adapter.py` (excluded from coverage — live credentials)
- **Use**: PE ratio, PB ratio, div_yield, revenue_growth → ML features (23 features total as of V2.5)
- **Note**: historically sparse for Swiss tickers; partially replaced by SIX filings

## SNB (Swiss National Bank)
- **Adapter**: `backend/infrastructure/adapters/snb_adapter.py`
- **Use**: Macro rates (CHF libor, policy rate) for macro signal layer

## SendGrid (Email Alerts)
- **Key**: `SENDGRID_API_KEY` env var
- **Use**: Alert notifications (`backend/infrastructure/workers/alert_worker.py`)
- **Adapter**: `backend/infrastructure/adapters/notification_adapter.py`

## Coin Metrics Community API ← PLANNED (V4-1)
- **Library**: direct HTTP via `httpx`
- **Use**: On-chain data — MVRV-Z, realized cap, active addresses, exchange netflow
- **Target tables**: `crypto_onchain_history` (migration 0038)
- **Coverage**: strong for BTC/ETH, thin for altcoins — On-Chain factor optional/weighted

## alternative.me Fear & Greed Index ← PLANNED (V4-1)
- **Use**: Daily crypto fear/greed score (historical + live) → sentiment feature
- **Target table**: `market_sentiment` (migration 0039)
- **Endpoint**: `https://api.alternative.me/fng/` (no auth, free)

## PostgreSQL + pgvector (Database)
- **Host**: Render.com free tier (`prisma-v2-db`, PostgreSQL 16)
- **Driver**: `asyncpg` via SQLAlchemy async engine
- **Connection**: `DATABASE_URL` env var (auto-normalised `postgresql://` → `postgresql+asyncpg://` in `backend/config.py`)
- **pgvector**: `CREATE EXTENSION vector` required after first deploy; `vector(1024)` columns for embeddings
- **Migrations**: Alembic `backend/alembic/versions/` — 22 migrations (0001–0022); next V4-1 = 0037–0039

## Render.com (Deployment)
- **Config**: `render.yaml`
- **Services**:
  - `prisma-v2-backend` — Docker web service, auto-deploy on `main`, health check `/health`
  - `prisma-v2-frontend` — Docker web service, `NEXT_PUBLIC_API_URL` baked at build
  - `prisma-news-ingestion` — Cron job, daily 06:00 UTC
- **No custom auth layer** — API key via `X-API-Key` header (`API_KEY` env var for admin endpoints)

## MCP Server
- **Entry**: `backend/interfaces/mcp/server.py`
- **Tools dir**: `backend/interfaces/mcp/tools/`
- **Auth**: `TOOL_API_KEY` env var (separate from admin `API_KEY`)
- **Pattern**: thin wrapper over application services — no business logic in MCP layer
- **Client**: `backend/interfaces/mcp/rest_client.py`

## RSS News
- **Adapter**: `backend/infrastructure/adapters/rss_news_adapter.py`
- **Use**: News ingestion (daily cron) → embeddings → RAG corpus for SteuerAgent / MacroAgent
