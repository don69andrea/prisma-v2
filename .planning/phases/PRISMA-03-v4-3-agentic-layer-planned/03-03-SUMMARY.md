---
plan: 03-03
phase: 03-v4-3-agentic-layer
status: complete
completed: 2026-06-22
tdd: true
---

# Plan 03-03: Four Analyst Agents — Summary

## What Was Built

Four parallel analyst agents (D-01 analyst layer) following the SteuerAgent gold-standard pattern.

### Agent Files Created

- `backend/application/agents/technical_analyst_agent.py` — TechnicalAnalystAgent (Haiku)
- `backend/application/agents/onchain_analyst_agent.py` — OnChainAnalystAgent (Haiku, tool stubs)
- `backend/application/agents/sentiment_analyst_agent.py` — SentimentAnalystAgent (DB stub, no LLM)
- `backend/application/agents/macro_regime_agent.py` — MacroRegimeAgent (Haiku, 1h cache)

### Jinja2 Prompts Created

- `backend/infrastructure/llm/prompts/technical_analyst.de.md.j2`
- `backend/infrastructure/llm/prompts/onchain_analyst.de.md.j2`
- `backend/infrastructure/llm/prompts/sentiment_analyst.de.md.j2`
- `backend/infrastructure/llm/prompts/macro_regime.de.md.j2`

### Test File Created

- `backend/tests/unit/application/test_analyst_agents.py` — 29 tests, all green

## TDD Gate

RED commit: `d41edba` — failing tests for all 4 agents
GREEN commit: `91aad9f` — full implementation

## Test Coverage

| Test | Status |
|------|--------|
| Hallucination guard (Technical) — output float == sub_scores float, diff < 1e-9 | ✓ |
| Hallucination guard (OnChain) — confidence == tool value, diff < 1e-9 | ✓ |
| TechnicalAnalystAgent: valid TechnicalView from mocked LLM | ✓ |
| TechnicalAnalystAgent: fallback on LLM Exception (confidence 0.4, no raise) | ✓ |
| TechnicalAnalystAgent: Literal violation → ValidationError → fallback | ✓ |
| OnChainAnalystAgent: valid OnChainView from mocked LLM | ✓ |
| OnChainAnalystAgent: fallback on Exception | ✓ |
| OnChainAnalystAgent: Literal violation → fallback | ✓ |
| SentimentAnalystAgent: fg=0 → score=-1.0 | ✓ |
| SentimentAnalystAgent: fg=50 → score=0.0 | ✓ |
| SentimentAnalystAgent: fg=100 → score=1.0 | ✓ |
| SentimentAnalystAgent: regime FEAR/NEUTRAL/GREED thresholds | ✓ |
| SentimentAnalystAgent: stub fields (news_surprise=None, veto=False, sources=[]) | ✓ |
| MacroRegimeAgent: valid MacroRegime output | ✓ |
| MacroRegimeAgent: 2 calls → 1 LLM call (cache TTL 1h) | ✓ |
| MacroRegimeAgent: fallback NEUTRAL on LLM Exception | ✓ |
| MacroRegimeAgent: Haiku model asserted | ✓ |
| MacroRegimeAgent: does NOT import MacroIntelligenceAgent | ✓ |

## Critical Requirements Met

- All 4 agents use `_MODEL = "claude-haiku-4-5-20251001"` (Haiku routing)
- Hallucination guard covers Technical AND OnChain (D-06 test 1 foundation)
- SentimentAnalystAgent: pure DB stub, score=(fg-50)/50, no LLM call
- MacroRegimeAgent: NEW file, 1h TTL cache, does not touch MacroIntelligenceAgent
- All agents: deterministic fallback on any Exception, confidence=0.4

## Deviations

- `agent_schemas.py` was present in worktree base (Wave 1 was merged before worktree fork)
- MacroRegimeAgent uses module-level dict cache with timestamp (vs functools.lru_cache) to allow clear_cache() in tests

## Self-Check: PASSED
