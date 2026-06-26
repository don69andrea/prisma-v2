---
phase: 03-v4-3-agentic-layer
plan: 01
subsystem: domain/schemas
tags: [pydantic, schemas, agent-contracts, tdd, d-05, d-06]
dependency_graph:
  requires: []
  provides:
    - "backend.domain.schemas.agent_schemas.TechnicalView"
    - "backend.domain.schemas.agent_schemas.OnChainView"
    - "backend.domain.schemas.agent_schemas.SentimentView"
    - "backend.domain.schemas.agent_schemas.MacroRegime"
    - "backend.domain.schemas.agent_schemas.BullCase"
    - "backend.domain.schemas.agent_schemas.BearCase"
    - "backend.domain.schemas.agent_schemas.RiskVerdict"
    - "backend.domain.schemas.agent_schemas.TradeSignal"
  affects:
    - "backend/application/agents/* (all agents in Phase 3)"
    - "backend/interfaces/rest/schemas/ (D-07 REST endpoint)"
    - "backend/infrastructure/persistence/ (audit trail repo)"
tech_stack:
  added:
    - "pydantic.BaseModel with Field(ge=..., le=...) bounds on all floats"
    - "typing.Literal for all enum fields (no-freetext enforcement)"
    - "uuid.UUID for audit_trail_id (non-optional)"
  patterns:
    - "TDD Red-Green: test written before implementation, import-error in RED"
    - "from __future__ import annotations (codebase convention)"
    - "_TRADE_DISCLAIMER constant (mirrors _DISCLAIMER in steuer_schema.py)"
key_files:
  created:
    - "backend/domain/schemas/agent_schemas.py"
    - "backend/tests/unit/domain/test_agent_schemas.py"
  modified: []
decisions:
  - "D-05 schema spec followed verbatim from 03-CONTEXT.md — no deviations"
  - "Disclaimer stored as module-level constant _TRADE_DISCLAIMER for reuse"
  - "SentimentView.sources typed list[str] (not list[dict]) matching D-04 stub contract"
  - "BullCase.risks_acknowledged and BearCase.counter_to_bull use list[str] per D-05"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-21T20:34:57Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
  tests_added: 59
  tests_passing: 59
---

# Phase 03 Plan 01: Agent Pydantic Schemas (D-05 Contract Lock) Summary

**One-liner:** 8 Pydantic models (TechnicalView through TradeSignal) as the V4-3 agentic layer output contract, with UUID audit trail linkage, bounded floats, Literal enum guards, and 59 TDD tests.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 RED | Failing tests for all 8 agent schemas (import error) | d4fafb3 | backend/tests/unit/domain/test_agent_schemas.py |
| 1 GREEN | Implement agent_schemas.py with all 8 D-05 models | 2190f41 | backend/domain/schemas/agent_schemas.py |

## What Was Built

### `backend/domain/schemas/agent_schemas.py`

The single source of truth for all agent output contracts in Phase V4-3:

1. **TechnicalView** — `coin`, `stance: Literal["BULLISH","NEUTRAL","BEARISH"]`, `consensus: str`, `key_signals: list[str]`, `confidence: Field(ge=0,le=1)`, `reasoning: str`

2. **OnChainView** — `coin`, `valuation: Literal["CHEAP","FAIR","EXPENSIVE"]`, `network_health: Literal["STRONG","NEUTRAL","WEAK"]`, `confidence: Field(ge=0,le=1)`, `reasoning: str`

3. **SentimentView** — `coin`, `score: Field(ge=-1,le=1)`, `regime: Literal["FEAR","NEUTRAL","GREED"]`, `news_surprise: bool|None = None`, `veto: bool = False`, `reasoning: str`, `sources: list[str] = []`

4. **MacroRegime** — `regime: Literal["RISK_ON","NEUTRAL","RISK_OFF"]`, `drivers: list[str]`, `confidence: Field(ge=0,le=1)`, `reasoning: str`

5. **BullCase** — `thesis: str`, `strongest_points: list[str]`, `risks_acknowledged: list[str]`

6. **BearCase** — `thesis: str`, `strongest_points: list[str]`, `counter_to_bull: list[str]`

7. **RiskVerdict** — `approve: bool`, `max_size: Field(ge=0,le=1.5)`, `breaches: list[str]`, `reasoning: str`

8. **TradeSignal** — `coin: str`, `action: Literal["BUY","HOLD","SELL"]`, `size_factor: Field(ge=0,le=1.5)`, `confidence: Field(ge=0,le=1)`, `rationale_by_layer: dict[str,str]`, `audit_trail_id: uuid.UUID` (required, not Optional), `disclaimer: str = "Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."`

### `backend/tests/unit/domain/test_agent_schemas.py`

59 tests covering:
- Valid construction for all 8 models with typical values
- Boundary value tests (0.0, 1.0, -1.0, 1.5) for all bounded floats
- **No-freetext guards (D-06 test 5)**: every Literal field tested with an invalid out-of-enum value → `ValidationError` asserted
- `TradeSignal.audit_trail_id` required (missing field raises `ValidationError`)
- UUID coercion from string input accepted by Pydantic
- Default disclaimer exact German string verified
- No-shorting: SELL action with `size_factor=0.0` is valid; `size_factor >= 0.0` always

## Deviations from Plan

None — plan executed exactly as written. D-05 schema spec from 03-CONTEXT.md followed verbatim.

## TDD Gate Compliance

- RED gate commit: `d4fafb3` — `test(03-01)` — failing test file with import error
- GREEN gate commit: `2190f41` — `feat(03-01)` — implementation, all 59 tests pass
- REFACTOR: not needed (schemas are pure data contracts, no logic to clean up)

## Acceptance Criteria — All Passed

- [x] `python3 -c "from backend.domain.schemas.agent_schemas import TechnicalView, OnChainView, SentimentView, MacroRegime, BullCase, BearCase, RiskVerdict, TradeSignal"` exits 0
- [x] All 59 schema tests green (`python3 -m pytest backend/tests/unit/domain/test_agent_schemas.py -q`)
- [x] Each Literal field rejects an invalid enum value (`ValidationError` asserted in tests)
- [x] `TradeSignal.disclaimer` default equals `"Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."`
- [x] `TradeSignal.audit_trail_id` typed `uuid.UUID`, not Optional, required at construction

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. Pure in-memory Pydantic schema definitions — no threat surface.

## Known Stubs

None — this plan creates schema definitions only (no data wiring, no placeholder values).

## Self-Check: PASSED

- FOUND: backend/domain/schemas/agent_schemas.py
- FOUND: backend/tests/unit/domain/test_agent_schemas.py
- FOUND: commit d4fafb3 (RED)
- FOUND: commit 2190f41 (GREEN)
- All 59 tests pass
