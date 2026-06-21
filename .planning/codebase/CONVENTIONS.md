---
title: CONVENTIONS
date: 2026-06-21
last_mapped_commit: ""
---

# Code Conventions — PRISMA V2

## Python (Backend)

**Toolchain:** ruff 0.15.11 (lint + format), mypy strict, Python 3.12+

**Lint rules (ruff):** `E, F, I, UP, B, SIM` — E501 and B008 ignored repo-wide
(B008 exception: FastAPI `Depends()` in default args is canonical pattern).

**Formatter:** `ruff format`, line-length = 100. ⚠️ macOS arm64 vs. Linux x86_64 may
differ at exactly 100 chars — always trust CI over local on macOS.

**Type annotations:** mandatory on all functions and methods (`mypy strict`).
`from __future__ import annotations` at top of every module.
Alembic migrations exempt from mypy (`exclude = ["backend/alembic/"]`).

**Naming:**
- `snake_case` for modules, functions, variables
- `PascalCase` for classes and Pydantic models
- Private helpers: leading underscore `_helper_fn`

**Imports:** isort via ruff, `known-first-party = ["backend"]`.
Group: stdlib → third-party → `backend.*`

**Async pattern (mandatory):**
```python
# CORRECT
result = await asyncio.to_thread(sync_fn, arg)
# WRONG — never use run_in_executor in this repo
```

**Retry pattern:** manual (`_RETRIES = 2`, `_BASE_DELAY = 1.0`, exponential backoff).
No `tenacity`. Pattern from `backend/infrastructure/adapters/yfinance_swiss.py`.

**Money/Decimal:** use `Decimal` for CHF amounts. Never bare `float` for currency.

**Datetime:** always UTC-aware. Never naive datetimes.

**Conditionals:** `if market_cap is not None:` not `if market_cap:` (0 is valid).

## Pydantic (Iron Rule)

Every LLM output, every API response, every agent output → validated via Pydantic v2 `BaseModel`.
**No raw LLM free-text into frontend.** This is non-negotiable.

Agent pattern (SteuerAgent as gold standard):
1. Tool-Use loop → structured tool calls
2. Pydantic-validated output schema
3. Deterministic fallback when LLM throws

LLM feature rules:
- `claude-haiku-4-5-20251001` for fast tasks, `claude-sonnet-4-6` for research/synthesis
- Prompt caching: `cache_control: ephemeral` for repeated system prompts
- Tests: never hit live API in CI — use fixtures in `backend/tests/fixtures/llm/`

## FastAPI / REST Layer

- `HTTPException` with structured detail dict for all errors
- `try/except` in services, never in routers (routers delegate to services)
- All endpoints return typed Pydantic response models
- MCP layer (`backend/interfaces/mcp/`) is thin over application services — no business logic there

## Git / Branch Workflow

- **main**: protected, Render deploys from here; no direct push
- **develop**: integration branch; protected; feature PRs merge here first
- Branch naming: `feat/<name>`, `fix/<name>`, `docs/<name>`, `chore/<name>`
- Commit convention: `feat(scope): message`, `fix(scope): message`, `docs(scope): ...`
- PRs: max ~20 files; independent features → separate PRs; CI must be green; 1 review

## TypeScript / Next.js (Frontend)

**Framework:** Next.js 14.2, React 18, TypeScript 5.4, Tailwind 3.4
**UI:** Radix UI primitives, Recharts, lucide-react, class-variance-authority

- PascalCase for components and types/interfaces
- camelCase for hooks (`usePrismaMode.ts`), utils, API client functions
- No `any` types — use `unknown` + type guards or generated OpenAPI types
- API calls via typed client in `frontend/lib/api/` (not raw fetch in components)
- OpenAPI-generated types only — no inline type duplication

## CI Requirements

- All tests green (backend + frontend unit + Playwright E2E)
- Backend coverage ≥ 80% (`fail_under = 80` in pyproject.toml)
- `ruff check` + `ruff format --check` clean
- `mypy backend/` clean (strict)
- Frontend lint + build clean

## Architecture Rules (see AGENTS.md)

- Signal-Engine is deterministic — LLM agents interpret/explain outputs, never compute them
- Port/Adapter pattern: yfinance access via `SwissMarketDataProvider` port only
- No yfinance calls in application services — must go via infrastructure adapter
- LLM responses parsed with `response.content[0].text` then Pydantic, never forwarded raw
