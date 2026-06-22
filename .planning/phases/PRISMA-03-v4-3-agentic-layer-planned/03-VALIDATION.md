---
phase: "03"
phase-slug: "v4-3-agentic-layer"
date: "2026-06-21"
---

# Phase 03 — Validation Strategy

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest backend/tests/unit/application/ -q -x` |
| Full suite command | `pytest backend/tests/ -q --cov=backend --cov-report=term-missing` |

## Phase Requirements → Test Map (D-06 Mandatory 7)

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| D-06-1 | Hallucination-Guard: every float in agent output == engine/tool float (diff < 1e-9) | unit | `pytest backend/tests/unit/application/test_signal_director.py::test_hallucination_guard -x` | Wave 0 |
| D-06-2 | State-from-Tool: RiskAgent reads exposure from mocked Store, no invented value | unit | `pytest ...::test_state_from_tool -x` | Wave 0 |
| D-06-3 | Minority-Protection: 1 Bear vs 3 Bulls → audit trail contains Bear case | unit | `pytest ...::test_minority_protection -x` | Wave 0 |
| D-06-4 | Fallback: LLM raises → TradeSignal returned, confidence lowered, disclaimer set | unit | `pytest ...::test_fallback_on_llm_error -x` | Wave 0 |
| D-06-5 | Pydantic-Schema: all agent outputs schema-validated; no freetext | unit | `pytest ...::test_pydantic_schema_all_agents -x` | Wave 0 |
| D-06-6 | Checkpoint: confidence < 0.65 → exactly 1 HITL call (logging.warning), non-blocking | unit | `pytest ...::test_checkpoint_trigger -x` | Wave 0 |
| D-06-7 | No-Shorting: action==SELL → size_factor==0.0 and max_size==0.0; never negative | unit | `pytest ...::test_no_shorting -x` | Wave 0 |
| REQ-3.3 | SentimentAnalystAgent reads real F&G from market_sentiment table (not hardcoded NEUTRAL) | unit | `pytest ...::test_sentiment_reads_db -x` | Wave 0 |
| REQ-3.8 | Audit trail immutability: 2 inserts → 2 rows, no UPDATE/DELETE method on repo | unit | `pytest ...::test_audit_trail_immutable -x` | Wave 0 |

All test files include `pytestmark = pytest.mark.unit` (pattern from `test_steuer_agent.py`).

## Sampling Rate

- **Per task commit:** `pytest backend/tests/unit/application/ -q -x`
- **Per wave merge:** `pytest backend/tests/ -q --cov=backend --cov-report=term-missing`
- **Phase gate:** Full suite green + coverage ≥ 80% before PR merge to develop

## Wave 0 Gaps (test files to create TDD-first)

- [ ] `backend/tests/unit/application/test_signal_director.py` — covers D-06-1 through D-06-7
- [ ] `backend/tests/unit/application/test_technical_analyst_agent.py`
- [ ] `backend/tests/unit/application/test_onchain_analyst_agent.py`
- [ ] `backend/tests/unit/application/test_sentiment_analyst_agent.py`
- [ ] `backend/tests/unit/application/test_macro_regime_agent.py`
- [ ] `backend/tests/unit/application/test_bull_bear_research_agents.py`
- [ ] `backend/tests/unit/application/test_risk_agent.py`

All use `AsyncMock` + `MagicMock` pattern from `backend/tests/unit/application/test_steuer_agent.py`.
