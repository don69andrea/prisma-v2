---
phase: 03-v4-3-agentic-layer
plan: 04
subsystem: agents
tags: [claude-tool-use, pydantic, bull-research, bear-research, risk-agent, sonnet, d-06, tdd, minority-protection, no-shorting, state-from-tool]

requires:
  - phase: 03-01
    provides: "agent_schemas.py — BullCase, BearCase, RiskVerdict Pydantic schemas"
  - phase: 03-03
    provides: "TechnicalView, OnChainView, SentimentView, MacroRegime — analyst views as inputs"

provides:
  - "backend.application.agents.bull_research_agent.BullResearchAgent.build_case() → BullCase via Tool-Use"
  - "backend.application.agents.bear_research_agent.BearResearchAgent.build_case() → BearCase via Tool-Use"
  - "backend.application.agents.risk_agent.RiskAgent.assess() → RiskVerdict (exposure from Store)"

affects:
  - "03-05 (SignalDirector calls bull/bear/risk in sequence)"
  - "03-06 (REST endpoint — triggers full pipeline)"

tech-stack:
  added:
    - "Claude Tool-Use API forced pattern (tool_choice={type:tool, name:...})"
    - "ExposureStore Protocol (D-06 test 2 State-from-Tool)"
  patterns:
    - "Tool-Use: tools=[{input_schema: Schema.model_json_schema()}] + forced tool_choice"
    - "D-06 test 7 No-Shorting: Python post-LLM max_size enforcement (if action==SELL: max_size=0.0)"
    - "D-06 test 2 State-from-Tool: exposure from Store BEFORE LLM call, injected into prompt"
    - "Minority Protection: Bull AND Bear always built, never short-circuited"
    - "Deterministic fallback on any Exception (approve=False, max_size=0.0)"

key-files:
  created:
    - "backend/application/agents/bull_research_agent.py"
    - "backend/application/agents/bear_research_agent.py"
    - "backend/application/agents/risk_agent.py"
    - "backend/infrastructure/llm/prompts/bull_research.de.md.j2"
    - "backend/infrastructure/llm/prompts/bear_research.de.md.j2"
    - "backend/infrastructure/llm/prompts/risk_agent.de.md.j2"
    - "backend/tests/unit/application/test_research_risk_agents.py"
    - "backend/domain/schemas/agent_schemas.py"
  modified: []

key-decisions:
  - "Model routing: all 3 agents use claude-sonnet-4-6 (research-grade synthesis, not Haiku)"
  - "Tool-Use pattern: tools=[{input_schema: BullCase.model_json_schema()}] + forced tool_choice, mirrors UniverseSuggestionService"
  - "D-06 test 2: ExposureStore Protocol injected in RiskAgent constructor; get_exposure() called before LLM, value passed into Jinja2 prompt context as current_exposure"
  - "D-06 test 7: Python post-LLM clamping in _enforce_no_shorting(); SELL→max_size=0.0; clamp [0.0, 1.5]"
  - "Fallback: any Exception → deterministic BullCase/BearCase/RiskVerdict (approve=False, max_size=0.0); no 500s"

requirements-completed: [REQ-3.5, REQ-3.6, REQ-3.10]

duration: 5min
completed: 2026-06-21
---

# Phase 03 Plan 04: BullResearchAgent, BearResearchAgent, RiskAgent Summary

**Three Sonnet Tool-Use debate agents (BullResearchAgent, BearResearchAgent, RiskAgent) with forced tool_choice, D-06 test 2 State-from-Tool exposure injection, and D-06 test 7 Python no-shorting enforcement — 21 TDD tests green.**

## Performance

- **Duration:** ~5 minutes
- **Started:** 2026-06-21T23:10:25Z
- **Completed:** 2026-06-21T23:15:48Z
- **Tasks:** 2 (Task 1: Bull/Bear RED+GREEN; Task 2: RiskAgent RED+GREEN)
- **Files created:** 8

## Accomplishments

- BullResearchAgent and BearResearchAgent both use forced Tool-Use API (`tool_choice={"type":"tool","name":"submit_bull_case/bear_case"}`) with `BullCase/BearCase.model_json_schema()` as `input_schema`; both use `claude-sonnet-4-6`
- RiskAgent reads portfolio exposure from injected `ExposureStore` BEFORE LLM call (D-06 test 2), injects real value into Jinja2 prompt context — LLM never hallucinates exposure
- Python post-LLM no-shorting enforcement: `if action=="SELL": max_size=0.0`; `max_size` clamped to `[0.0, 1.5]` (D-06 test 7)
- Minority protection: both Bull and Bear `build_case()` always return a valid case — no short-circuiting; both are always available for audit trail persistence
- Conservative deterministic fallback on any Exception: `approve=False`, `max_size=0.0`

## TDD Gate

- RED commit: `7eb5120` — `test(03-04)` — 21 failing tests (ModuleNotFoundError on all 3 agents)
- GREEN commit: `95be63d` — `feat(03-04)` — all implementations, 21 tests pass

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for Bull/Bear/Risk agents | 7eb5120 | backend/tests/unit/application/test_research_risk_agents.py, backend/domain/schemas/agent_schemas.py |
| 1+2 GREEN | BullResearchAgent, BearResearchAgent, RiskAgent + prompts | 95be63d | 3 agent files + 3 Jinja2 prompts |

## Test Coverage

| Test | D-06 | Status |
|------|------|--------|
| BullResearchAgent: valid BullCase from tool_use block | 1 (foundation) | ✓ |
| BullResearchAgent: tool_choice forcing asserted on call kwargs | — | ✓ |
| BullResearchAgent: tools list contains BullCase.model_json_schema() | — | ✓ |
| BullResearchAgent: model == claude-sonnet-4-6 | — | ✓ |
| BullResearchAgent: no tool_use block → fallback BullCase (no raise) | 4 (fallback) | ✓ |
| BearResearchAgent: valid BearCase from tool_use block | 1 (foundation) | ✓ |
| BearResearchAgent: tool_choice forcing asserted on call kwargs | — | ✓ |
| BearResearchAgent: tools list contains BearCase.model_json_schema() | — | ✓ |
| BearResearchAgent: model == claude-sonnet-4-6 | — | ✓ |
| BearResearchAgent: no tool_use block → fallback BearCase (no raise) | 4 (fallback) | ✓ |
| RiskAgent: valid RiskVerdict from tool_use block | — | ✓ |
| RiskAgent: exposure read from Store (D-06 test 2 State-from-Tool) | **2** | ✓ |
| RiskAgent: SELL → max_size == 0.0 (D-06 test 7 No-Shorting) | **7** | ✓ |
| RiskAgent: BUY → max_size >= 0.0 | **7** | ✓ |
| RiskAgent: HOLD → max_size >= 0.0 | **7** | ✓ |
| RiskAgent: approve False when breach present | — | ✓ |
| RiskAgent: LLM Exception → conservative verdict (no raise) | 4 (fallback) | ✓ |
| RiskAgent: model == claude-sonnet-4-6 | — | ✓ |
| RiskAgent: tool_choice forcing asserted | — | ✓ |
| RiskAgent: SELL → max_size=0.0 even if LLM returns positive | **7** | ✓ |
| RiskAgent: max_size >= 0.0 always (clamped) | **7** | ✓ |

## Files Created

- `backend/application/agents/bull_research_agent.py` — BullResearchAgent: forced Tool-Use, sonnet, BullCase extraction, fallback
- `backend/application/agents/bear_research_agent.py` — BearResearchAgent: forced Tool-Use, sonnet, BearCase extraction, fallback
- `backend/application/agents/risk_agent.py` — RiskAgent: ExposureStore injection, State-from-Tool, no-shorting enforcement, conservative fallback
- `backend/infrastructure/llm/prompts/bull_research.de.md.j2` — Jinja2 prompt for bullish one-sided thesis
- `backend/infrastructure/llm/prompts/bear_research.de.md.j2` — Jinja2 prompt for bearish one-sided thesis
- `backend/infrastructure/llm/prompts/risk_agent.de.md.j2` — Jinja2 prompt injecting current_exposure from Store
- `backend/tests/unit/application/test_research_risk_agents.py` — 21 tests (TDD RED then GREEN)
- `backend/domain/schemas/agent_schemas.py` — Dependency from plan 01 (not in worktree base)

## Decisions Made

1. **Model routing:** `claude-sonnet-4-6` for all 3 agents (research-grade, not Haiku) per plan critical requirements.
2. **Tool-Use pattern:** Mirrored `UniverseSuggestionService` exactly: `BullCase.model_json_schema()` as `input_schema`, `tool_choice={"type":"tool","name":"submit_bull_case"}`, extract `block.type=="tool_use"`, `BullCase.model_validate(block.input)`.
3. **ExposureStore Protocol:** Injected in RiskAgent constructor; `get_exposure()` called before any LLM invocation; value stored in local var `current_exposure` and passed to `prompt_loader.render()` as context key — test asserts this context key equals the mocked store value.
4. **No-Shorting enforcement:** Separate `_enforce_no_shorting()` static method called after LLM response extraction AND after fallback; returns new `RiskVerdict` with corrected `max_size` — immutable update pattern.
5. **agent_schemas.py in worktree:** This worktree was forked from `11ed54a` (before plan 01 was merged). agent_schemas.py was copied from main repo content (identical to plan 01's GREEN commit).

## Deviations from Plan

### Auto-included Dependency

**[Rule 3 - Blocking] Created agent_schemas.py in worktree**
- **Found during:** Pre-task setup
- **Issue:** Worktree forked from `11ed54a` (before Phase 03 Wave 1 merged). `agent_schemas.py` not present in worktree working tree.
- **Fix:** Created `backend/domain/schemas/agent_schemas.py` with identical content to plan 01's GREEN commit (`2190f41`) — same 8 Pydantic schemas verbatim.
- **Files modified:** backend/domain/schemas/agent_schemas.py
- **Committed in:** 7eb5120 (RED commit, as dependency alongside test file)

---

**Total deviations:** 1 (dependency injection, not a code change)
**Impact on plan:** Required to unblock tests; content is byte-for-byte identical to plan 01's delivered contract.

## Issues Encountered

- 3 pre-existing test failures in `test_dependencies.py` and `test_config.py` (Pydantic Settings `ANTHROPIC_API_KEY` validation in production mode) — unrelated to plan 04, not introduced by this plan.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. All agents are pure in-memory Pydantic + async Python — no DB access, no HTTP calls (LLM calls go through existing LLMClient wrapper).

## Known Stubs

None — all 3 agents produce real structured outputs from real LLM calls (mocked in tests). No placeholder values flow to UI. Prompt templates reference real input fields from analyst views.

## Next Phase Readiness

- SignalDirector (plan 05) can now call `bull.build_case(...)`, `bear.build_case(...)`, `risk.assess(...)` in its LLM loop
- Both Bull and Bear always return a valid case — no short-circuiting; both available for audit trail persistence (minority protection satisfied)
- RiskAgent `ExposureStore` protocol ready for wiring to real portfolio repository in plan 05/06

## Self-Check: PASSED

- FOUND: backend/application/agents/bull_research_agent.py
- FOUND: backend/application/agents/bear_research_agent.py
- FOUND: backend/application/agents/risk_agent.py
- FOUND: backend/infrastructure/llm/prompts/bull_research.de.md.j2
- FOUND: backend/infrastructure/llm/prompts/bear_research.de.md.j2
- FOUND: backend/infrastructure/llm/prompts/risk_agent.de.md.j2
- FOUND: backend/tests/unit/application/test_research_risk_agents.py
- FOUND: commit 7eb5120 (RED)
- FOUND: commit 95be63d (GREEN)
- All 21 tests pass: `python3 -m pytest backend/tests/unit/application/test_research_risk_agents.py -q` → 21 passed
