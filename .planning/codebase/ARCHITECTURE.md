---
date: 2026-06-21
focus: arch
---

# PRISMA V2 — Architecture

## Pattern: Hexagonal / Clean Architecture

The codebase follows a strict four-layer hexagonal architecture. Dependencies point inward only: interfaces and infrastructure depend on application, application depends on domain, domain depends on nothing.

```
┌──────────────────────────────────────────────────────┐
│  INTERFACES  (FastAPI REST + MCP)                    │
│  backend/interfaces/rest/   backend/interfaces/mcp/  │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│  APPLICATION  (Services + Agents)                    │
│  backend/application/services/                       │
│  backend/application/agents/                         │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│  INFRASTRUCTURE  (Adapters + Persistence + LLM)      │
│  backend/infrastructure/adapters/                    │
│  backend/infrastructure/persistence/                 │
│  backend/infrastructure/llm/                         │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│  DOMAIN  (Entities + Value Objects + Schemas)        │
│  backend/domain/entities/                            │
│  backend/domain/value_objects/                       │
│  backend/domain/schemas/                             │
│  backend/domain/services/                            │
└──────────────────────────────────────────────────────┘
```

## Backend Data Flow

**Standard request:**
```
HTTP Request
  → backend/interfaces/rest/routers/<router>.py
  → backend/application/services/<service>.py
  → backend/infrastructure/persistence/repositories/<repo>.py
  → PostgreSQL (via SQLAlchemy async)
  → Pydantic response schema
  → HTTP Response
```

**LLM-Agent request:**
```
HTTP Request
  → Router (e.g. backend/interfaces/rest/routers/steuer.py)
  → Agent (e.g. backend/application/agents/steuer_agent.py)
    ├─ Tool: RetrievalService (RAG, pgvector)
    ├─ Tool: LLMClient (backend/infrastructure/llm/client.py)
    └─ Pydantic validation (domain schema)
  → Pydantic-validated output → stored/returned
```

## LLM-Agent Pattern (SteuerAgent as Gold Standard)

`backend/application/agents/steuer_agent.py` is the canonical reference for all new agents. Key properties:
- Constructor injection of `LLMClient`, `RetrievalService`, `PromptTemplateLoader`
- Tool-Use loop: all data comes from tools/services, never from LLM memory
- Output is always Pydantic-schema-validated (`SteuerEinschätzung`)
- Deterministic fallback on LLM error — never raises 500
- Mandatory disclaimer on every output
- Model: `claude-sonnet-4-6` (sonnet for synthesis, haiku for analysts)

## Frontend Architecture

```
frontend/app/                    ← Next.js 14 App Router
  layout.tsx                     ← root layout, Providers
  providers.tsx                  ← ReactQuery QueryClientProvider
  page.tsx                       ← landing/redirect
  [route]/page.tsx               ← Server Component (data fetch boundary)
  [route]/[route]-client.tsx     ← Client Component (interactive UI)

frontend/lib/api/<resource>.ts   ← typed API clients (fetch wrappers)
frontend/components/             ← shared UI components
frontend/hooks/                  ← custom React hooks (e.g. usePrismaMode)
```

Data flow: Server Component fetches via `frontend/lib/api/*.ts` → passes to Client Component → React Query manages client-side caching/refetch.

All API types are generated from backend Pydantic schemas (OpenAPI). No `any` types in API clients.

## Key Planned Abstractions (V4-1, not yet built)

```python
# backend/application/signals/signal_service.py (planned)
class SignalVector(BaseModel):
    coin: str
    asof: date
    action: Literal["BUY", "HOLD", "SELL"]
    size_factor: float                    # 0.0–1.5
    consensus: str                        # e.g. "3/3"
    sub_scores: dict[str, float]
    confidence: float
    disclaimer: str

# backend/application/backtest/walkforward.py (planned)
class BacktestReport(BaseModel):
    coin: str; cagr: float; sharpe: float
    max_dd: float; calmar: float
    beats_exposure_matched: bool
    n_trades: int; equity_curve: list[tuple[date, float]]
```

## Database

PostgreSQL with pgvector extension. Async access via SQLAlchemy 2.0 + asyncpg. ORM models in `backend/infrastructure/persistence/models/`. Schema managed with Alembic migrations (0001–0022 as of 2026-06-21).

## CI / Testing Strategy

- Backend: pytest-asyncio, SQLite (aiosqlite) for unit tests, real DB for integration tests
- Frontend: Jest + React Testing Library, Playwright for E2E
- Coverage gate: ≥80% enforced in CI
- Lint: ruff (Python), ESLint + TypeScript strict (TS)
