---
phase: 03-v4-3-agentic-layer
plan: "05"
subsystem: agentic-layer
tags: [signal-director, orchestration, tdd, fallback, hitl, audit-trail, minority-protection]
dependency_graph:
  requires: ["03-01", "03-02", "03-03", "03-04"]
  provides: ["SignalDirector.run(coin) -> TradeSignal"]
  affects: ["backend/application/agents/signal_director.py"]
tech_stack:
  added: []
  patterns:
    - asyncio.gather(return_exceptions=True) for parallel analyst invocation with fallback
    - asyncio.to_thread() for sync engine call (CLAUDE.md convention)
    - Pure Python weighted synthesis (no LLM in _synthesize)
    - model_copy(update=...) for immutable Pydantic patching
key_files:
  created:
    - backend/application/agents/signal_director.py
    - backend/tests/unit/application/test_signal_director.py
  modified: []
decisions:
  - "_synthesize() is pure Python (weighted confidence), not an LLM call — determinism + testability"
  - "bear_case is always serialized into agent_run dict regardless of bull/bear balance (minority protection)"
  - "HITL checkpoint is non-blocking: logging.warning once + disclaimer prefix, no UI interaction"
  - "Fallback confidence penalty is -0.15 (additive) when any analyst exception occurs"
metrics:
  duration_minutes: 25
  completed_date: "2026-06-22"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  tests_added: 9
  tests_passing: 9
---

# Phase 03 Plan 05: SignalDirector — Orchestration Hub Summary

**One-liner:** `SignalDirector.run(coin)` orchestrates engine + 4 parallel analysts + bull/bear/risk into a resilient, HITL-checkpointed, fully audited `TradeSignal` with pure-Python weighted synthesis.

## What Was Built

`SignalDirector` is the D-01 pipeline core. It implements the complete hybrid orchestration sequence:

1. `engine_signal = await asyncio.to_thread(signal_service.evaluate, coin, ...)` — sync engine wrapped per CLAUDE.md
2. `tech, onchain, senti, macro = await asyncio.gather(..., return_exceptions=True)` — parallel, exception-safe
3. Sequential: `bull = await bull_agent.build_case(...)`, `bear = await bear_agent.build_case(...)`, `risk = await risk_agent.assess(...)`
4. `_synthesize(...)` — pure Python weighted confidence (7 weights summing to 1.0), all 7 rationale keys built
5. HITL checkpoint: `if signal.confidence < 0.65` → `logging.warning(...)` once + disclaimer prefix (non-blocking)
6. `agent_run = {all 8 outputs as .model_dump()}` → `audit_id = await repo.insert(coin, asof, agent_run)`
7. `TradeSignal.model_copy(update={"audit_trail_id": audit_id})` — real UUID embedded before return

## Test Results

All 9 unit tests pass (RED → GREEN):

| Test | D-06 | Status |
|------|------|--------|
| `test_run_returns_valid_trade_signal` | — | PASS |
| `test_synthesis_rationale_by_layer_has_all_7_keys` | — | PASS |
| `test_no_shorting_max_size_zero_propagates_to_size_factor` | — | PASS |
| `test_audit_trail_id_is_real_uuid_from_repo` | — | PASS |
| `test_fallback_analyst_exception_still_returns_trade_signal` | D-06 test 4 | PASS |
| `test_checkpoint_low_confidence_triggers_exactly_one_warning` | D-06 test 6 | PASS |
| `test_minority_protection_bear_case_always_in_agent_run` | D-06 test 3 | PASS |
| `test_all_8_outputs_in_agent_run` | — | PASS |
| `test_repo_insert_called_once_per_run` | — | PASS |

## TDD Gate Compliance

- RED commit: `623a583` — `test(03-05): add failing tests for SignalDirector (RED)`
- GREEN commit: `8af55ef` — `feat(03-05): implement SignalDirector orchestration hub (GREEN)`

Both gates present and in correct order.

## Success Criteria

- [x] run(coin) → TradeSignal with real audit_trail_id UUID from repo.insert
- [x] rationale_by_layer: all 7 keys present (technical, onchain, sentiment, macro, bull, bear, risk)
- [x] No-shorting: RiskVerdict.max_size 0.0 → size_factor 0.0
- [x] D-06 test 4 (fallback): analyst Exception → TradeSignal, confidence lowered
- [x] D-06 test 6 (checkpoint): confidence < 0.65 → 1 warning call, disclaimer prefix
- [x] D-06 test 3 (minority): bear_case in agent_run when bulls dominate
- [x] repo.insert called once; UUID in TradeSignal
- [x] All 9 tests green

## Deviations from Plan

**1. [Rule 3 - Blocking] Copied prior-plan files into worktree**
- **Found during:** Pre-test setup — worktree missing `agent_schemas.py`, agent files, ORM model, and `agent_audit_trail_repository.py`
- **Fix:** Copied from main repo: `agent_schemas.py`, 7 agent files, `agent_audit_trail.py` ORM, `agent_audit_trail_repository.py`
- **Files modified:** 10 additional files added to worktree (not new implementations, just worktree sync)
- **Commits:** included in RED commit `623a583`

## Known Stubs

None — all synthesis is functional; audit trail UUID is real from repo.insert.

## Threat Flags

None — `SignalDirector` does not introduce new network endpoints or auth paths.

## Self-Check

- [x] `backend/application/agents/signal_director.py` exists
- [x] `backend/tests/unit/application/test_signal_director.py` exists
- [x] RED commit `623a583` in git log
- [x] GREEN commit `8af55ef` in git log
- [x] 9 tests passing

## Self-Check: PASSED
