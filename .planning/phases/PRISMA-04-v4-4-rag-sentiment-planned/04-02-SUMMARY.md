---
phase: 04-v4-4-rag-sentiment-planned
plan: "02"
subsystem: testing / migration
tags: [migration, tdd, red-stubs, wave-0, cryptopanic, sentiment, backtest]
dependency_graph:
  requires: []
  provides:
    - migration-0042-widen-source-varchar20
    - wave0-red-stubs-domain-entities
    - wave0-red-stubs-schema
    - wave0-red-stubs-config
    - wave0-red-stubs-score-formula
    - wave1-red-stubs-adapter
    - wave1-red-stubs-ingestion
    - wave3-red-stubs-backtest
  affects:
    - backend/alembic/versions/
    - backend/tests/unit/domain/entities/
    - backend/tests/unit/domain/schemas/
    - backend/tests/unit/application/
    - backend/tests/unit/infrastructure/
    - backend/tests/integration/
tech_stack:
  added: []
  patterns:
    - parametrize-boundary-value-testing
    - red-green-refactor-tdd
    - alembic-alter-column-migration
    - c02-votes-metadata-guard
key_files:
  created:
    - backend/alembic/versions/0042_widen_news_source_column.py
    - backend/tests/unit/domain/entities/test_news_article.py
    - backend/tests/unit/domain/entities/test_news_retrieval_result.py
    - backend/tests/unit/domain/schemas/test_agent_schemas.py
    - backend/tests/unit/test_settings.py
    - backend/tests/unit/application/test_sentiment_score_formula.py
    - backend/tests/unit/infrastructure/test_cryptopanic_adapter.py
    - backend/tests/unit/application/test_news_ingestion_cryptopanic.py
    - backend/tests/integration/test_backtest_sentiment_comparison.py
  modified: []
decisions:
  - "Migration 0042 widens news_documents.source VARCHAR(10) to VARCHAR(20) — only news_documents has a source column (news_chunks does not), confirmed by reading 0014_create_news_tables.py"
  - "news_chunks has no source column — migration is single-table alter_column on news_documents only"
  - "Backtest integration test uses multi-coin fixture covering BTC/ETH/SOL/BNB/XRP (all Top-Coins) as required by special instructions"
  - "C-02 guard implemented: test_news_ingestion_cryptopanic.py asserts chunk metadata carries BOTH votes_positive AND votes_negative"
  - "Score formula test uses exact constants: _VETO_SCORE_THRESHOLD=-0.3, _FEAR_THRESHOLD=-0.2, _MIN_ARTICLES_FOR_VOTE_RATIO=5"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-22T14:08:18Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 9
  files_modified: 0
---

# Phase 04 Plan 02: Migration 0042 + Wave-0 RED Test Stubs Summary

**One-liner:** Alembic migration 0042 widening news_documents.source VARCHAR(10)→VARCHAR(20) plus 8 RED TDD stub files covering domain entities (CRYPTOPANIC source, url field), schema (SentimentLLMOutput), config (sentiment_enabled), score formula (D-03 blend/fallback/regime/veto), adapter parsing, ingestion (C-02 votes guard), and multi-coin backtest comparison (BTC/ETH/SOL/BNB/XRP).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Alembic migration 0042 — widen source to VARCHAR(20) | 16f4426 | backend/alembic/versions/0042_widen_news_source_column.py |
| 2 | Wave-0 RED stubs — domain, schema, config, score formula | bcd336f | 5 test files in unit/domain/entities, unit/domain/schemas, unit/, unit/application |
| 3 | Wave-1/2/3 RED stubs — adapter, ingestion, backtest | 1c2d1ae | 3 test files in unit/infrastructure, unit/application, integration |

## What Was Built

### Task 1: Migration 0042

- `backend/alembic/versions/0042_widen_news_source_column.py`
- `revision="0042"`, `down_revision="0041"` (chains from agent_audit_trail migration)
- `upgrade()`: `op.alter_column("news_documents", "source", type_=sa.String(20), existing_type=sa.String(10), nullable=False)`
- `downgrade()`: reverses to String(10)
- Only `news_documents` is widened — `news_chunks` has no `source` column (confirmed by reading 0014)
- Resolves blocker B-04, D-07: "CRYPTOPANIC" (11 chars) exceeds old VARCHAR(10) limit

### Task 2: Wave-0 RED Stubs

**test_news_article.py** (entities/)
- Asserts `source="CRYPTOPANIC"` is accepted (REQ-4-03)
- Asserts NZZ/SRF still accepted (non-regression)
- Asserts "UNKNOWN" and "REUTERS" still rejected
- RED: fails until plan 04-01 adds "CRYPTOPANIC" to `_VALID_SOURCES`

**test_news_retrieval_result.py** (entities/)
- Asserts `url: str` field exists and round-trips (REQ-4-04)
- RED: fails until plan 04-01 adds `url` field to `NewsRetrievalResult`

**test_agent_schemas.py** (schemas/)
- Asserts `SentimentLLMOutput` importable from agent_schemas (REQ-4-06)
- Asserts exactly `{news_surprise, reasoning}` fields (§0 Iron Rule enforcement)
- Asserts non-bool `news_surprise` rejected by Pydantic strict validation
- RED: fails until plan 04-01 adds `SentimentLLMOutput` to agent_schemas.py

**test_settings.py** (unit/)
- Asserts `sentiment_enabled: bool = False` default (REQ-4-09)
- Asserts `SENTIMENT_ENABLED=true` env var → `True`
- RED: fails until plan 04-01 adds `sentiment_enabled` field to config.py

**test_sentiment_score_formula.py** (application/)
- 23 parametrized tests covering:
  - D-03 blend formula: `0.7*(pos-neg)/max(1,pos+neg) + 0.3*(fg-50)/50` (5 parametrized cases)
  - D-03 fallback: `fg_norm = (fg-50)/50` when < `_MIN_ARTICLES_FOR_VOTE_RATIO=5` (5 cases)
  - Regime boundaries at `_FEAR_THRESHOLD=-0.2` and `+0.2` (5 cases)
  - D-05 veto truth table: all 8 combos of (FEAR, news_surprise, score < `_VETO_SCORE_THRESHOLD=-0.3`) (8 cases)
- Uses exact constants: `_VETO_SCORE_THRESHOLD=-0.3`, `_FEAR_THRESHOLD=-0.2`, `_MIN_ARTICLES_FOR_VOTE_RATIO=5`
- RED: all 23 fail until plan 04-05 upgrades SentimentAnalystAgent

### Task 3: Wave-1/2/3 RED Stubs

**test_cryptopanic_adapter.py** (infrastructure/)
- Static JSON fixture (no live API)
- Asserts `votes_positive=11`, `votes_negative=2`, `currencies=["BTC"]` parsing (REQ-4-01)
- Asserts malformed JSON → `[]` (T-4-02); missing `results` key → `[]`; empty results → `[]`
- RED: fails until plan 04-03 implements CryptoPanicAdapter

**test_news_ingestion_cryptopanic.py** (application/)
- C-02 guard (Pitfall 6): chunk metadata must carry BOTH `votes_positive` AND `votes_negative`
- Asserts `save_article` called with `source="CRYPTOPANIC"` (REQ-4-02)
- Asserts articles published > 7 days ago are skipped (D-02 TTL)
- Asserts recent articles (< 7d) are ingested
- RED: fails until plan 04-04 implements `ingest_cryptopanic()`

**test_backtest_sentiment_comparison.py** (integration/)
- Multi-coin fixture: BTC, ETH, SOL, BNB, XRP (all Top-Coins)
- Asserts `SENTIMENT_ENABLED=true` + `veto=True` → action="HOLD" for BNB/XRP
- Asserts `SENTIMENT_ENABLED=false` → veto ignored
- Asserts negative score reduces `size_factor` (downside-only scaling)
- Asserts positive score does NOT amplify `size_factor` beyond baseline
- Asserts vetoed trade count ≥ 2 (BNB + XRP)
- Asserts all 5 Top-Coins produce results (REQ-4-10)

## Deviations from Plan

None — plan executed exactly as written.

## RED Confirmation

| File | Status | Reason |
|------|--------|--------|
| test_sentiment_score_formula.py | RED (23/23 fail) | SentimentAnalystAgent V4-4 constructor requires 4 args not yet added |
| test_cryptopanic_adapter.py | RED (9/9 fail) | CryptoPanicAdapter does not exist yet |
| test_news_ingestion_cryptopanic.py | RED (9/9 fail) | ingest_cryptopanic() not implemented yet |
| test_backtest_sentiment_comparison.py | RED at collection/runtime | compare_sentiment_backtest module not yet implemented |
| test_news_article.py | RED | "CRYPTOPANIC" not in _VALID_SOURCES yet |
| test_news_retrieval_result.py | RED | url field not added yet |
| test_agent_schemas.py | RED | SentimentLLMOutput not yet in agent_schemas |
| test_settings.py | RED | sentiment_enabled not yet in config |

## Known Stubs

These test files are intentionally stub/RED files. They will turn GREEN in later plans:
- Wave-0 entity/schema/config stubs → GREEN in plan 04-01
- Score formula stubs → GREEN in plan 04-05
- Adapter stubs → GREEN in plan 04-03
- Ingestion stubs → GREEN in plan 04-04
- Backtest stubs → GREEN in plan 04-07

## Threat Flags

None — this plan creates only migration DDL and test files. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond the single `ALTER COLUMN` documented in T-4-DB.

## Self-Check

### Created files exist:
- FOUND: backend/alembic/versions/0042_widen_news_source_column.py
- FOUND: backend/tests/unit/domain/entities/test_news_article.py
- FOUND: backend/tests/unit/domain/entities/test_news_retrieval_result.py
- FOUND: backend/tests/unit/domain/schemas/test_agent_schemas.py
- FOUND: backend/tests/unit/test_settings.py
- FOUND: backend/tests/unit/application/test_sentiment_score_formula.py
- FOUND: backend/tests/unit/infrastructure/test_cryptopanic_adapter.py
- FOUND: backend/tests/unit/application/test_news_ingestion_cryptopanic.py
- FOUND: backend/tests/integration/test_backtest_sentiment_comparison.py

### Commits verified:
- 16f4426: chore(04-02): create migration 0042
- bcd336f: test(04-02): add Wave-0 RED stubs
- 1c2d1ae: test(04-02): add Wave-1/2/3 RED stubs

### Migration verified:
- Contains `alter_column`, `"0042"`, `"0041"`, `String(20)` ✓
- Parses without syntax error ✓
- `down_revision = "0041"` chains correctly ✓

### Test stubs RED confirmed:
- test_sentiment_score_formula.py: 23 failed (exit 1) ✓
- test_cryptopanic_adapter.py + test_news_ingestion_cryptopanic.py: 18 failed (exit 1) ✓

## Self-Check: PASSED
