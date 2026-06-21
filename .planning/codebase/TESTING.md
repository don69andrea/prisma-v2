---
title: TESTING
date: 2026-06-21
last_mapped_commit: ""
---

# Testing — PRISMA V2

## Framework & Config

**Backend:** pytest 8.1+, pytest-asyncio 0.23+ (`asyncio_mode = "auto"`)
**Coverage:** pytest-cov, `fail_under = 80`, branch=false
**Lint in CI:** ruff + mypy run before tests
**Frontend unit:** Vitest (via `npx vitest run`)
**Frontend E2E:** Playwright (`frontend/e2e/`)

## Test Structure

```
backend/tests/
  conftest.py                     # shared fixtures: InMemoryStockRepository, http_client
  fixtures/llm/
    stub_anthropic_client.py      # LLM stub — never hits live API in CI
    fixture_llm_client.py
  unit/
    application/                  # service layer tests (no I/O)
      test_signal_aggregation_service.py
      test_backtest_service.py
      test_discovery_service.py
      test_macro_agent.py
      test_steuer_agent.py
      test_narrative_service.py
      test_ml_prediction_service.py
      ... (30+ files)
    domain/                       # pure domain logic tests
      entities/                   # entity invariants
      models/                     # scoring model tests (alpha, quality, trend)
      schemas/
      test_swiss_quant_scorer.py
      test_eligibility_filter.py
    infrastructure/               # adapter tests (no live network)
      test_yfinance_swiss_adapter.py
      test_six_filings_adapter.py
      test_pricing.py
    interfaces/
      rest/
      mcp/
  integration/
    conftest.py                   # real SQLAlchemy engine against DB
    persistence/                  # repository integration tests
    test_*_endpoint.py            # HTTP layer tests via httpx AsyncClient + ASGITransport
```

## Pytest Markers

```python
pytestmark = pytest.mark.unit        # mandatory in all unit test files
pytestmark = pytest.mark.integration # for integration tests requiring DB/HTTP
```

Run selectively:
```bash
pytest backend/tests/unit -q -m unit
pytest backend/tests/integration -q -m integration  # requires running DB
```

## Async Tests

All async tests use `@pytest.mark.asyncio` (auto-mode means no decorator needed in most cases).
`@pytest_asyncio.fixture` for async fixtures.

```python
@pytest.mark.asyncio
async def test_get_signal_buy_eligible() -> None:
    ...
```

## Mocking Patterns

**Services via AsyncMock (standard pattern):**
```python
from unittest.mock import AsyncMock

feature_svc = AsyncMock()
feature_svc.build_features.return_value = _make_features(quant_score=80.0)
```

**Factory helpers (preferred over pytest fixtures for complex objects):**
```python
def _make_features(ticker: str = "NESN", quant_score: float = 72.0) -> MLFeatureVector:
    return MLFeatureVector(ticker=ticker, ...)  # all fields specified

def _make_repo(stock: SwissStock | None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_ticker.return_value = stock
    return repo
```

**HTTP mocking:** `httpx_mock` for external HTTP calls, or `ASGITransport` for in-process FastAPI.

**LLM stubs:** `backend/tests/fixtures/llm/stub_anthropic_client.py` — always use this,
never hit live Anthropic API in CI tests.

## Integration Test Pattern

Uses real SQLAlchemy async engine against test DB:
```python
# backend/tests/integration/conftest.py
@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(settings.database_url, ...)
    factory = async_sessionmaker(bind=engine, ...)
    yield factory
    await engine.dispose()
```

In-memory HTTP testing (no DB needed for HTTP-layer tests):
```python
# backend/tests/conftest.py — InMemoryStockRepository + ASGITransport pattern
app.dependency_overrides[get_stock_repository] = lambda: in_memory_repo
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
    yield client
```

## Coverage Configuration

```toml
[tool.coverage.run]
source = ["backend"]
omit = [
    "backend/tests/*",
    "backend/alembic/*",
    # External API adapters requiring live credentials
    "backend/infrastructure/adapters/simfin_adapter.py",
    # MCP server entry point (tested via integration)
    "backend/interfaces/mcp/server.py",
]
fail_under = 80
```

## Frontend Tests

**Unit (Vitest):** `frontend/app/**/__tests__/`, `frontend/components/**/__tests__/`, `frontend/lib/api/__tests__/`
**E2E (Playwright):** `frontend/e2e/` — smoke tests for key flows (rankings, memo, alerts, stocks, discovery)

Key E2E files:
- `frontend/e2e/02-ranking.spec.ts`
- `frontend/e2e/04-memo.spec.ts`
- `frontend/e2e/06-alerts.spec.ts`
- `frontend/e2e/13-discovery.spec.ts`
- `frontend/e2e/rankings.spec.ts`

## TDD Rule (AGENTS.md mandate)

For domain code, quant models, application services: write tests BEFORE implementation.
Red → Green → Refactor. New signals/indicators must have unit tests before any service code.

## V4-1 Specific Test Requirements (from PRISMA_V4-1_PHASENPLAN_Signal-Engine.md §A7)

New tests to add in `backend/tests/unit/application/signals/`:
1. Indicator correctness vs `ta`-lib reference (Δ < 1e-6)
2. Look-ahead guard (signal@t uses only data ≤ t−1)
3. Consensus voting truth-table (2-of-3)
4. Vol-forecast walk-forward OOS-R² > 0 on ≥2 coins
5. Sizing monotonicity (higher vol → smaller size_factor)
6. Backtest baselines computed correctly; `beats_exposure_matched` flag
7. Net costs applied (strategy return < gross on turnover)
8. No-shorting: action=="SELL" ⇒ target exposure = 0
9. API schema: all endpoints return valid Pydantic (no free-text)
10. Coverage gate ≥80% maintained
