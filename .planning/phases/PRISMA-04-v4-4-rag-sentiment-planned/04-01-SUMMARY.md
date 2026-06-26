---
phase: 04-v4-4-rag-sentiment-planned
plan: "01"
subsystem: domain-entities-schema-config
tags: [tdd, domain, entities, schema, config, cryptopanic, sentiment, rag]
dependency_graph:
  requires: []
  provides:
    - CRYPTOPANIC in _VALID_SOURCES (backend/domain/entities/news_article.py)
    - url field on NewsRetrievalResult (backend/domain/entities/news_retrieval_result.py)
    - nd.url in find_nearest() SELECT (backend/infrastructure/persistence/repositories/news_repository.py)
    - max_age_days TTL filter in find_nearest() (backend/infrastructure/persistence/repositories/news_repository.py)
    - SentimentLLMOutput schema (backend/domain/schemas/agent_schemas.py)
    - sentiment_enabled config flag (backend/config.py)
  affects:
    - All downstream plans (04-02 through 04-07) that depend on Wave 0 blockers
    - CryptoPanicAdapter ingestion (04-04)
    - SentimentAnalystAgent (04-05)
    - SignalDirector veto wiring (04-06)
tech_stack:
  added: []
  patterns:
    - TDD RED→GREEN for domain + schema changes
    - Pydantic strict bool (model_config strict=True) for §0 Iron Rule enforcement
    - Bound parameters for SQL TTL filter (AGENTS.md §7/§8)
    - pydantic-settings env var auto-read for boolean flag
key_files:
  created:
    - backend/tests/unit/domain/entities/test_news_retrieval_result.py
    - backend/tests/unit/test_settings.py
  modified:
    - backend/domain/entities/news_article.py
    - backend/domain/entities/news_retrieval_result.py
    - backend/infrastructure/persistence/repositories/news_repository.py
    - backend/domain/schemas/agent_schemas.py
    - backend/config.py
    - backend/tests/unit/domain/test_news_article.py
    - backend/tests/unit/domain/test_agent_schemas.py
    - backend/tests/unit/application/test_news_retrieval_service.py
    - backend/tests/integration/test_news_endpoint.py
decisions:
  - sentiment_enabled defaults False per D-06 CRITICAL USER REQUIREMENT (SENTIMENT_ENABLED=false)
  - SentimentLLMOutput uses model_config strict=True to enforce §0 Iron Rule (no numeric coercion)
  - url field placed after title in NewsRetrievalResult dataclass (keyword arg compatible per B-02)
  - max_age_days TTL uses bound parameter INTERVAL '1 day' * :max_age_days (not string-concat)
metrics:
  duration: "~6 minutes"
  completed: "2026-06-22"
  tasks_completed: 3
  files_changed: 9
---

# Phase 04 Plan 01: Domain Entities + Schema + Config Foundations Summary

Wave 0 blockers B-01, B-02, and the SentimentLLMOutput schema (D-04) plus sentiment_enabled flag (D-06) landed as interface contracts for all downstream waves.

## Tasks Completed

| Task | Type | Commit | Description |
|------|------|--------|-------------|
| 1 RED | TDD | 01c54e5 | Failing tests for CRYPTOPANIC + NewsRetrievalResult.url |
| 1 GREEN | TDD | 7c16830 | CRYPTOPANIC in _VALID_SOURCES + url: str on NewsRetrievalResult |
| 2 | execute | b80cdbc | nd.url in find_nearest() SELECT + max_age_days TTL filter |
| 3 RED | TDD | 7e3e06f | Failing tests for SentimentLLMOutput + sentiment_enabled |
| 3 GREEN | TDD | 2313161 | SentimentLLMOutput strict:bool schema + sentiment_enabled=False |
| fix | Rule1 | ff5ae6e | Backward-compat fix for existing test fixtures broken by url field |

## What Was Built

**Task 1:** Extended `_VALID_SOURCES = frozenset({"NZZ", "SRF", "CRYPTOPANIC"})` in `news_article.py` (B-01). Added `url: str` field after `title: str` in `NewsRetrievalResult` (B-02). Existing NZZ/SRF sources still valid (regression-guarded).

**Task 2:** `find_nearest()` now selects `nd.url` and maps it as `url=str(row["url"])` in result construction. Added `max_age_days: int | None = None` parameter — when set, appends `AND nd.published_at > NOW() - INTERVAL '1 day' * :max_age_days` using a bound parameter (never string-concat per AGENTS.md §7/§8). Backward-compatible: `max_age_days=None` preserves existing NZZ/SRF behavior.

**Task 3:** `SentimentLLMOutput(BaseModel)` added to `agent_schemas.py` with `model_config = {"strict": True}` — enforces strict bool validation (LLM cannot emit a string "maybe" or int 1 for `news_surprise`). Exactly two fields: `news_surprise: bool` and `reasoning: str`. Added to `__all__`. `SentimentView` is frozen and unchanged. `sentiment_enabled: bool = False` added to `Settings` class in `config.py` — pydantic-settings auto-reads `SENTIMENT_ENABLED` env var; default is False (CRITICAL: matches SENTIMENT_ENABLED=false requirement).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Backward-compat fix for NewsRetrievalResult consumers**
- **Found during:** Task 1 GREEN + post-task regression run
- **Issue:** Adding `url: str` field to the frozen dataclass breaks all existing instantiation sites that do not pass `url=` keyword. Two test files raised `TypeError: __init__() missing 1 required positional argument: 'url'`.
- **Fix:** Added `url=` with representative URL strings to existing fixtures in `test_news_retrieval_service.py` and `test_news_endpoint.py`.
- **Files modified:** `backend/tests/unit/application/test_news_retrieval_service.py`, `backend/tests/integration/test_news_endpoint.py`
- **Commit:** ff5ae6e

**2. [Rule 2 - Missing] Pydantic deprecation in test**
- **Found during:** Task 3 GREEN run
- **Issue:** `out.model_fields` (instance access) triggered Pydantic v2.11 deprecation warning. CLAUDE.md: warnings must not be ignored.
- **Fix:** Changed to `SentimentLLMOutput.model_fields` (class access).
- **Files modified:** `backend/tests/unit/domain/test_agent_schemas.py`
- **Commit:** 2313161 (inline during GREEN)

## Pre-existing Failures (Out of Scope)

3 pre-existing unit test failures unrelated to this plan (confirmed via git diff showing no modifications to these files):
- `test_dependencies.py::test_get_fundamentals_provider_production_logs_warning`
- `test_dependencies.py::test_get_market_data_provider_production_logs_warning`
- `test_config.py::test_passes_when_api_key_set_in_production` (missing anthropic_api_key in production test setup)

These are logged in `deferred-items.md` for tracking but not fixed (scope boundary).

## Known Stubs

None. All changes are concrete implementations with no placeholder values.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes at trust boundaries introduced. `SentimentLLMOutput` is the mitigated T-4-03 threat (Pydantic strict bool prevents LLM from injecting numeric values).

## Self-Check: PASSED

Files exist:
- backend/domain/entities/news_article.py: FOUND (CRYPTOPANIC in _VALID_SOURCES)
- backend/domain/entities/news_retrieval_result.py: FOUND (url: str field)
- backend/infrastructure/persistence/repositories/news_repository.py: FOUND (nd.url + max_age_days)
- backend/domain/schemas/agent_schemas.py: FOUND (class SentimentLLMOutput + in __all__)
- backend/config.py: FOUND (sentiment_enabled: bool = False)

Commits exist (all on worktree-agent-ac1160269f0517d5f):
- 01c54e5: test RED for Task 1
- 7c16830: feat GREEN for Task 1
- b80cdbc: feat Task 2
- 7e3e06f: test RED for Task 3
- 2313161: feat GREEN for Task 3
- ff5ae6e: fix Rule 1 backward-compat

Tests passing: 18/18 (Task 1), 4/4 (Task 2 verify), 71/71 (Task 3 full suite), 1096/1099 unit suite (3 pre-existing failures)
