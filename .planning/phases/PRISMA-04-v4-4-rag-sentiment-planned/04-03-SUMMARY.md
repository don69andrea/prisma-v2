---
phase: 04-v4-4-rag-sentiment-planned
plan: "03"
subsystem: infrastructure/adapters
tags: [cryptopanic, news-rag, adapter, tdd, httpx, retry, votes]
dependency_graph:
  requires: ["04-01", "04-02"]
  provides: ["cryptopanic_adapter.py — CryptoPanicAdapter + RawCryptoPanicArticle"]
  affects: ["04-04 — NewsIngestionService.ingest_cryptopanic()", "04-05 — D-03 vote-ratio score"]
tech_stack:
  added: []
  patterns:
    - "RssNewsAdapter retry/backoff pattern (verbatim) — _RETRY_BACKOFF=[1.0,2.0,4.0]"
    - "Frozen dataclass for raw API output (RawCryptoPanicArticle)"
    - "Defensive JSON parsing: _fetch_raw returns {} on JSONDecodeError → _parse_response returns []"
    - "votes.get('positive', 0) / votes.get('negative', 0) for A2 safety (missing votes default to 0)"
key_files:
  created:
    - backend/infrastructure/adapters/cryptopanic_adapter.py
    - backend/tests/unit/infrastructure/test_cryptopanic_adapter.py
  modified: []
decisions:
  - "Catch JSON errors in _fetch_raw() returning {} (not re-raise), so _parse_response({}) naturally returns [] — cleaner separation than catching in fetch_articles()"
  - "Added 3 test cases beyond 04-02 stub: missing votes subfield, partial votes, _MAX_ARTICLES cap (plan said 'flesh out if stub is thin')"
  - "asyncio.sleep() for retry backoff (not time.sleep — CLAUDE.md rule)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-22T14:20:29Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 04 Plan 03: CryptoPanicAdapter TDD — Summary

**One-liner:** CryptoPanicAdapter with defensive JSON parsing, votes defaulting to 0, _MAX_ARTICLES=50 cap, and RssNewsAdapter-identical retry/backoff — 12 unit tests green.

## Tasks Completed

| # | Name | Type | Commit | Status |
|---|------|------|--------|--------|
| 1 | CryptoPanicAdapter.fetch_articles() — TDD JSON parsing | tdd | ecd68d8 | GREEN |

## What Was Built

**`backend/infrastructure/adapters/cryptopanic_adapter.py`** (182 lines):
- `RawCryptoPanicArticle` — frozen dataclass with `url`, `title`, `published_at` (UTC-aware `datetime|None`), `votes_positive: int`, `votes_negative: int`, `currencies: list[str]`
- `CryptoPanicAdapter` — async HTTP adapter with constructor injection of `httpx.AsyncClient` (testable without network)
- `fetch_articles(coin: str) -> list[RawCryptoPanicArticle]` — retry loop verbatim from `RssNewsAdapter` with `asyncio.sleep()` backoff
- `_fetch_raw(params)` — calls `GET https://cryptopanic.com/api/v1/posts/` with `auth_token=free`; catches `json.JSONDecodeError` + `httpx.DecodingError` → returns `{}` (T-4-02 mitigation)
- `_parse_response(raw_json)` — extracts `votes.get("positive", 0)` / `votes.get("negative", 0)` (A2 safety), `currencies[].code`, caps to `_MAX_ARTICLES=50`
- `_parse_datetime(raw)` — ISO-8601 → UTC-aware `datetime` via `datetime.fromisoformat().astimezone(UTC)`

**`backend/tests/unit/infrastructure/test_cryptopanic_adapter.py`** (244 lines):
- `TestCryptoPanicAdapterParsing` — 6 tests (votes_positive=11, votes_negative=2, currencies=["BTC"], url, title, multi-currency)
- `TestCryptoPanicAdapterErrorHandling` — 3 tests (JSONDecodeError→[], missing results key→[], empty results→[])
- `TestCryptoPanicAdapterSafetyRules` — 3 tests added (missing votes subfield→0/0, partial votes→positive=0, _MAX_ARTICLES cap)

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED | n/a (pre-existing stub from 04-02; confirmed ModuleNotFoundError before implementation) | confirmed RED |
| GREEN | ecd68d8 | 12/12 PASS |
| REFACTOR | not needed — `_parse_response()` already extracted as module-level function | n/a |

## Verification Results

```
pytest backend/tests/unit/infrastructure/test_cryptopanic_adapter.py -x
12 passed in 0.03s

pytest backend/tests/unit/infrastructure/ -q
149 passed in 0.57s
```

Acceptance criteria:
- `class CryptoPanicAdapter` present: PASS
- `class RawCryptoPanicArticle` present: PASS
- `auth_token` present: PASS
- `_RETRY_BACKOFF = [1.0, 2.0, 4.0]` present: PASS
- No `run_in_executor`: PASS
- No `time.sleep`: PASS
- `_MAX_ARTICLES = 50` present: PASS
- File >= 60 lines (182): PASS
- UTC-aware datetime: PASS

## Deviations from Plan

### Auto-added Tests (Plan says "flesh out if stub is thin")

**1. [Rule 2 - Missing Critical Functionality] Added 3 safety/cap test cases**
- **Found during:** Task 1 RED phase inspection
- **Issue:** 04-02 stub had 9 tests but was missing: A2 safety (missing votes → 0), partial votes (only negative present), _MAX_ARTICLES enforcement
- **Fix:** Added `TestCryptoPanicAdapterSafetyRules` class with 3 additional tests covering these behaviors
- **Files modified:** `backend/tests/unit/infrastructure/test_cryptopanic_adapter.py`
- **Commit:** ecd68d8 (same commit as implementation)

No other deviations — plan executed as written.

## Known Stubs

None — this plan implements a complete infrastructure adapter with no placeholder behavior.

## Threat Flags

None — no new network endpoints or auth paths introduced beyond what was planned. The `auth_token=free` parameter is a CryptoPanic public API convention (D-01), not a credential.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `backend/infrastructure/adapters/cryptopanic_adapter.py` | FOUND |
| `backend/tests/unit/infrastructure/test_cryptopanic_adapter.py` | FOUND |
| `.planning/phases/PRISMA-04-v4-4-rag-sentiment-planned/04-03-SUMMARY.md` | FOUND |
| Commit `ecd68d8` | FOUND |
