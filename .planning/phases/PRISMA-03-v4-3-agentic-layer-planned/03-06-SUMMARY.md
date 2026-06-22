---
phase: 03-v4-3-agentic-layer
plan: "06"
subsystem: agentic-layer
tags: [rest-endpoint, agentic-pipeline, mandatory-tests, coverage-gate, d06]
dependency_graph:
  requires: [03-01, 03-02, 03-03, 03-04, 03-05]
  provides: [agent-signal-endpoint, d06-mandatory-suite, coverage-gate]
  affects: [signals-router, dependencies-di-chain, test-coverage]
tech_stack:
  added:
    - "GET /api/v1/agent-signal/{coin} REST endpoint (FastAPI, TradeSignal response_model)"
    - "get_signal_director() Depends factory with full 8-agent DI chain"
  patterns:
    - "404 allowlist guard (_CRYPTO_UNIVERSE) — matches existing get_signal pattern"
    - "503 LLM-outage map — matches existing get_backtest pattern"
    - "Stub ExposureStore (0.0 exposure) in DI factory — real store wired in V4-4"
key_files:
  created:
    - backend/interfaces/rest/routers/signals.py (agent_router added)
    - backend/interfaces/rest/dependencies.py (get_signal_director added)
    - backend/interfaces/rest/app.py (agent_router registered)
    - backend/tests/integration/test_agent_signal_endpoint.py (4 endpoint tests)
    - backend/tests/integration/test_agent_mandatory_suite.py (7 D-06 tests)
    - backend/application/agents/signal_director.py (ported from main branch)
    - backend/application/agents/technical_analyst_agent.py (ported)
    - backend/application/agents/onchain_analyst_agent.py (ported)
    - backend/application/agents/sentiment_analyst_agent.py (ported)
    - backend/application/agents/macro_regime_agent.py (ported)
    - backend/application/agents/bull_research_agent.py (ported)
    - backend/application/agents/bear_research_agent.py (ported)
    - backend/application/agents/risk_agent.py (ported)
    - backend/domain/schemas/agent_schemas.py (ported)
    - backend/infrastructure/persistence/models/agent_audit_trail.py (ported)
    - backend/infrastructure/persistence/repositories/agent_audit_trail_repository.py (ported)
  modified: []
decisions:
  - "agent_router uses separate prefix /api/v1/agent-signal to avoid path conflict with signals router /{coin}"
  - "get_signal_director() inlines StubExposureStore (returns 0.0) — real ExposureStore wired V4-4"
  - "Prior plan artifacts (03-01 to 03-05) ported into worktree via file copy from main branch feat/v4-3-agentic-layer"
  - "Coverage measured with non-DB tests; 82.47% achieved (pre-existing DB failures excluded)"
metrics:
  duration: "~45 minutes"
  completed: "2026-06-22"
  tasks: 2
  files: 19
---

# Phase 03 Plan 06: REST Endpoint + D-06 Mandatory Suite — Summary

REST endpoint `GET /api/v1/agent-signal/{coin}` exposed to the full V4-3 agentic pipeline; all 7 mandatory D-06 compliance tests assembled and green; coverage gate 82.47% >= 80% satisfied.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | GET /api/v1/agent-signal/{coin} endpoint + DI factory + ported agent layer | `9566611` | Done |
| 2 | All 7 D-06 mandatory tests in test_agent_mandatory_suite.py | `81bbaa7` | Done |

## What Was Built

### Task 1: REST Endpoint + DI Factory

Added `agent_router = APIRouter(prefix="/api/v1/agent-signal")` to `signals.py` with:
- `GET /{coin}`: uppercases coin, validates against `_CRYPTO_UNIVERSE` allowlist (404 on miss), calls `await director.run(coin_upper)`, maps any exception to HTTP 503 matching the existing `get_backtest` 503 pattern.
- `response_model=TradeSignal` — Pydantic schema enforced at boundary.

`get_signal_director()` in `dependencies.py`:
- Constructs all 8 agents (TechnicalAnalystAgent, OnChainAnalystAgent, SentimentAnalystAgent, MacroRegimeAgent, BullResearchAgent, BearResearchAgent, RiskAgent, SignalDirector).
- All agents take `llm_client` + `prompt_loader` via constructor injection.
- RiskAgent gets a `_StubExposureStore` (returns 0.0 — wired to real store in V4-4).
- SentimentAnalystAgent takes `db_session` (reads market_sentiment table).
- `AgentAuditTrailRepository(session=session)` for audit persistence.

Registered `agent_router` in `app.py` with same `_auth` dependencies as other signal routers.

**Endpoint Tests (4 green):**
- 200 + TradeSignal body for known coin (`BTC-USD`)
- Lowercase normalisation (`btc-usd` -> `BTC-USD`)
- 404 for unknown coin (`FOO`)
- 503 when `director.run()` raises RuntimeError

### Task 2: D-06 Mandatory Suite

All 7 mandatory compliance tests in `backend/tests/integration/test_agent_mandatory_suite.py`:

| Test | D-06 # | Key Assertion |
|------|--------|---------------|
| `test_d06_1_hallucination_guard` | #1 | `abs(signal.size_factor - min(engine.size, risk.max)) < 1e-9`; both TechnicalView AND OnChainView confidence propagated (separate zero-confidence sub-assertions per each) |
| `test_d06_2_state_from_tool` | #2 | `ExposureStore.get_exposure(COIN)` called before `llm.messages_create`; verdict from structured output not hallucinated |
| `test_d06_3_minority_protection` | #3 | `"bear_case" in agent_run` even vs 3 bullish analysts; `"Regulatory crackdown"` in stored thesis; Risk can reduce `size_factor` to 0.0 |
| `test_d06_4_fallback` | #4 | All 4 analysts raise -> `TradeSignal` returned; `confidence < no_fallback.confidence`; `action` valid; no exception propagates |
| `test_d06_5_pydantic_schema` | #5 | All 8 schemas reject freetext Literal violations and type errors; valid instances pass |
| `test_d06_6_checkpoint` | #6 | `signal.confidence < 0.65`; >=1 `logging.warning` call with "LOW CONFIDENCE"; disclaimer starts with "LOW CONFIDENCE"; non-blocking |
| `test_d06_7_no_shorting` | #7 | `SELL + max_size=0.0 -> size_factor==0.0`; `BUY + max_size=0.0 -> size_factor==0.0`; never negative |

**Coverage: 82.47% >= 80% gate — PASS**

## Deviations from Plan

### Auto-fixes Applied

**1. [Rule 3 - Blocking] Worktree missing 03-01 to 03-05 agent artifacts**
- **Found during:** Task 1 setup
- **Issue:** Worktree was branched from commit `11ed54a` (v4-2 Meta-Labeling), before plans 03-01 through 03-05 were merged into `feat/v4-3-agentic-layer` on the main repo. All agent files were absent.
- **Fix:** Copied all 9 agent/schema files + 2 infrastructure files + 3 existing test files from the main repo (commit `fa58120`) into the worktree.
- **Files modified:** 14 files added to worktree
- **Commit:** `9566611`

**2. [Rule 2 - Missing Critical] StubExposureStore in DI factory**
- **Found during:** Task 1 — `RiskAgent.__init__` requires an `ExposureStore` Protocol
- **Issue:** No real ExposureStore is wired in V4-3 (deferred to V4-4). DI factory would fail without a concrete implementation.
- **Fix:** Added inline `_StubExposureStore` class in `get_signal_director()` returning `0.0` exposure (safe default).
- **Commit:** `9566611`

## Coverage Gate

```
Total coverage: 82.47%
Required: 80%
Status: PASSED
```

Pre-existing DB-dependent test failures (persistence, narrative service, RAG) require a running PostgreSQL instance and are not counted against coverage.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `_StubExposureStore` (returns 0.0) | `backend/interfaces/rest/dependencies.py` | Real ExposureStore wired in V4-4 once portfolio DB table exists |

## Self-Check: PASSED

- [x] `backend/tests/integration/test_agent_signal_endpoint.py` exists, 4 tests green
- [x] `backend/tests/integration/test_agent_mandatory_suite.py` exists, 7 tests green
- [x] `backend/interfaces/rest/routers/signals.py` contains `agent-signal`
- [x] Commits `9566611` and `81bbaa7` exist in git log
- [x] Coverage 82.47% >= 80%
- [x] All 7 D-06 assertions present and not weakened
- [x] No STATE.md / ROADMAP.md modified
