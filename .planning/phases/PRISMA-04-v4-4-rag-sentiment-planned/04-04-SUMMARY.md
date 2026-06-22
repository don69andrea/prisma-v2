---
phase: 04-v4-4-rag-sentiment-planned
plan: "04"
subsystem: news-ingestion
tags: [rag, sentiment, cryptopanic, ingestion, tdd, votes-metadata]
dependency_graph:
  requires: ["04-01", "04-02", "04-03"]
  provides: ["04-05", "04-06"]
  affects: ["backend/application/services/news_ingestion_service.py"]
tech_stack:
  added: []
  patterns: ["TDD RED/GREEN", "per-article try/except error isolation", "url_hash dedup", "7-day TTL", "chunk metadata votes"]
key_files:
  created:
    - backend/infrastructure/adapters/cryptopanic_adapter.py
    - backend/tests/unit/application/test_news_ingestion_cryptopanic.py
    - .planning/phases/PRISMA-04-v4-4-rag-sentiment-planned/04-04-PLAN.md
  modified:
    - backend/application/services/news_ingestion_service.py
    - backend/domain/entities/news_article.py
decisions:
  - "chunk metadata carries votes_positive + votes_negative (C-02 / Pitfall 6 guard)"
  - "CRYPTOPANIC added to _VALID_SOURCES in NewsArticle entity (Rule 3 fix)"
  - "DEFAULT_FEEDS unchanged per B-03 — RSS path not modified"
  - "CryptoPanicAdapter injected as optional constructor param (None default)"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-22"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 5
---

# Phase 04 Plan 04: NewsIngestionService.ingest_cryptopanic() Summary

**One-liner:** Added `ingest_cryptopanic(coins)` to `NewsIngestionService` with votes in chunk metadata (C-02), 7-day TTL (D-02), url_hash dedup (D-02), and CRYPTOPANIC source support — 9 TDD tests pass.

## What Was Built

`NewsIngestionService.ingest_cryptopanic(coins: list[str]) -> dict[str, int]` — a new method that:

1. Iterates over the given coin list, calling `self._cryptopanic.fetch_articles(coin)` for each
2. Applies a 7-day TTL filter (D-02): articles with `published_at < now - 7d` are skipped
3. Deduplicates via `url_hash` using `repo.exists_by_url_hash()` (D-02)
4. Creates `NewsArticle` with `source="CRYPTOPANIC"` and `tickers=raw.currencies` (no TickerNer per D-07)
5. Builds chunk metadata with **`votes_positive` and `votes_negative`** (C-02, Pitfall 6 guard) — critical for D-03 score computation in plan 04-05
6. Embeds chunks via `self._llm.embed(model="voyage-3-large")` and saves via `repo.save_chunks()`
7. Isolates per-article errors with try/except — increments `errors` counter without aborting the loop
8. Returns `{"ingested": N, "skipped_duplicate": N, "errors": N}` stats dict

## Commits

| Hash | Message |
|------|---------|
| fc1704e | feat(04-04): NewsIngestionService.ingest_cryptopanic() — TDD GREEN, 9 tests pass |

## Tests

All 9 tests in `backend/tests/unit/application/test_news_ingestion_cryptopanic.py` pass:

- `TestNewsIngestionCryptoPanicSource` (2 tests): source="CRYPTOPANIC", returns stats
- `TestNewsIngestionCryptoPanicVotesInChunkMetadata` (4 tests): votes_positive, votes_negative, values, source in metadata
- `TestNewsIngestionCryptoPanicTTL` (3 tests): old articles skipped, recent ingested, None published_at handled

Existing RSS ingestion tests (7 tests in `test_news_ingestion_service.py`) remain green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Bug] CRYPTOPANIC missing from NewsArticle._VALID_SOURCES**
- **Found during:** Task 1 GREEN phase — `NewsArticle.__post_init__` raised `ValueError: source must be one of ['NZZ', 'SRF']`
- **Issue:** This branch (`worktree-agent-aef940e7fa0469fd3`) branched from `main` before plan 04-01 ran on `feat/v4-4-rag-sentiment`, so `_VALID_SOURCES` only had `{"NZZ", "SRF"}`
- **Fix:** Added `"CRYPTOPANIC"` to `_VALID_SOURCES` in `backend/domain/entities/news_article.py`
- **Files modified:** `backend/domain/entities/news_article.py`
- **Commit:** fc1704e (same commit)

## Known Stubs

None — no placeholder data or stub values flow to UI rendering from this plan.

## Threat Flags

None — `ingest_cryptopanic()` follows same trust boundary pattern as `_ingest_feed()` (adapter → corpus). External content is embedded, not executed.

## Self-Check: PASSED

- [x] `backend/application/services/news_ingestion_service.py` exists and contains `async def ingest_cryptopanic`
- [x] `backend/infrastructure/adapters/cryptopanic_adapter.py` exists
- [x] `backend/tests/unit/application/test_news_ingestion_cryptopanic.py` exists (9 tests)
- [x] Commit `fc1704e` exists in git log
- [x] DEFAULT_FEEDS unchanged (NZZ + SRF only)
- [x] `votes_positive` and `votes_negative` present in chunk_metadata dict
- [x] 7-day TTL enforced via `cutoff = now - timedelta(days=_CRYPTOPANIC_TTL_DAYS)`
- [x] url_hash dedup via `exists_by_url_hash()`
- [x] `pytest backend/tests/unit/application/test_news_ingestion_cryptopanic.py -x` exits 0
