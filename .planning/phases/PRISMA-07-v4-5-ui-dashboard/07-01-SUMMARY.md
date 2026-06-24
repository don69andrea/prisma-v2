---
phase: "07"
plan: "07-01"
subsystem: "backend-api"
tags: ["fastapi", "sqlalchemy", "alembic", "tdd", "hitl", "ohlcv", "audit-trail"]
dependency_graph:
  requires: ["06-*"]
  provides: ["crypto_dashboard_router", "hitl_confirmations_table", "ohlcv_endpoint", "agent_audit_endpoint"]
  affects: ["frontend-dashboard", "v4-5-ui"]
tech_stack:
  added: ["hitl_confirmation ORM", "hitl_confirmation_repository", "crypto_dashboard router"]
  patterns: ["append-only repository", "TDD RED/GREEN", "DI via dependency_overrides", "asyncio.to_thread"]
key_files:
  created:
    - backend/infrastructure/persistence/models/hitl_confirmation.py
    - backend/infrastructure/persistence/repositories/hitl_confirmation_repository.py
    - backend/alembic/versions/0043_hitl_confirmations.py
    - backend/interfaces/rest/schemas/crypto_dashboard.py
    - backend/interfaces/rest/routers/crypto_dashboard.py
    - backend/tests/unit/infrastructure/test_hitl_confirmation_repository.py
    - backend/tests/unit/interfaces/test_crypto_dashboard_router.py
  modified:
    - backend/infrastructure/persistence/repositories/agent_audit_trail_repository.py
    - backend/tests/unit/infrastructure/test_agent_audit_trail_repository.py
    - backend/interfaces/rest/app.py
decisions:
  - "Soft FK on audit_trail_id in hitl_confirmations (no CASCADE) to avoid cross-migration dependency"
  - "DI factories (get_audit_trail_repo, get_hitl_repo, get_crypto_price_adapter) exposed for test override"
  - "HITL confirm endpoint returns 201 with decided_at=now(UTC) — no DB round-trip needed"
  - "Coin universe validated against frozenset in ohlcv and confirm endpoints"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-24"
  tasks_completed: 7
  files_changed: 10
---

# Phase 07 Plan 01: Backend API Endpoints for V4-5 Dashboard Summary

## One-liner

Three new read/append REST endpoints under `/api/v1/crypto/`: agent-audit trail lookup, OHLCV candlestick data via yfinance, and HITL confirm logging — with Alembic migration 0043 and full TDD coverage.

## What Was Built

### Task 1: HitlConfirmation ORM + Repository (TDD)
- `HitlConfirmationORM`: append-only SQLAlchemy model for `hitl_confirmations` table. UUID PK, soft FK `audit_trail_id`, `coin`, `decision` ("proceed"|"abort"), `decided_at` (UTC).
- `HitlConfirmationRepository`: exposes only `insert()` — no update, delete, or save.
- 3 unit tests (RED → GREEN): `test_insert_persists_decision`, `test_insert_aborts`, `test_multiple_confirms_for_same_audit`.

### Task 2: Alembic Migration 0043
- Creates `hitl_confirmations` table with index on `audit_trail_id`.
- No FK constraint (soft ref). Downgrade: drop index + table.

### Task 3: Pydantic Schemas
- `AgentRunDetail`: parses `agent_run` JSONB → typed views (TechnicalView, OnChainView, SentimentView, MacroRegime, BullCase, BearCase, RiskVerdict). All Optional.
- `AgentAuditResponse`, `OHLCVBar`, `OHLCVResponse`, `HitlConfirmRequest`, `HitlConfirmResponse`.
- Imports from `backend.domain.schemas.agent_schemas` — no `Any` types.

### Task 4: AgentAuditTrailRepository.find_latest_by_coin()
- Added `find_latest_by_coin(coin)` — SELECT by `coin.upper()` ORDER BY `created_at DESC LIMIT 1`.
- 2 new tests in existing test file: most-recent returned for 2 inserts, None for missing coin.

### Task 5: REST Router
- `backend/interfaces/rest/routers/crypto_dashboard.py`, prefix `/api/v1/crypto`.
- `GET /{coin}/agent-audit`: validates coin via repo, parses `agent_run` → `AgentRunDetail`, 404 if missing.
- `GET /{coin}/ohlcv?days=120`: validates against `_CRYPTO_UNIVERSE_COINS` frozenset, calls `CryptoPriceAdapter.fetch_ohlcv()`, maps DataFrame rows to `OHLCVBar` list.
- `POST /{coin}/confirm`: pure log, calls `HitlConfirmationRepository.insert()`, returns 201. No auto-trading.
- 6 unit tests (RED → GREEN): 2 audit, 2 ohlcv, 2 confirm.

### Task 6: Register Router
- `crypto_dashboard_router` added to `app.py` with `_auth` dependencies (same as other V4 routers).

### Task 7: All Tests Pass
- 19/19 unit tests pass across all 3 test files.

## Deviations from Plan

None — plan executed exactly as written.

The plan mentioned `backend/interfaces/rest/main.py` as the registration point. The actual registration point is `backend/interfaces/rest/app.py` (the plan had `main.py` as the uvicorn entry, but the factory is in `app.py`). Registration was done in the correct file (`app.py`).

## Known Stubs

None. All endpoints are fully wired:
- Agent audit endpoint reads from real `agent_audit_trail` table via repository.
- OHLCV endpoint calls `CryptoPriceAdapter` which uses yfinance.
- HITL confirm endpoint writes to `hitl_confirmations` table via repository.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: append_only_write | backend/interfaces/rest/routers/crypto_dashboard.py | POST /confirm writes to DB without authentication check in router — auth delegated to `_auth` dependency in app.py include_router call |

## Self-Check: PASSED

- [x] `HitlConfirmationORM` and `HitlConfirmationRepository` created and tested
- [x] Migration 0043 creates `hitl_confirmations` table
- [x] `AgentAuditTrailRepository.find_latest_by_coin()` tested
- [x] All 3 endpoints return Pydantic-validated responses (no `Any`)
- [x] OHLCV endpoint validates coin against `_CRYPTO_UNIVERSE_COINS`
- [x] HITL confirm endpoint has no auto-trading logic (pure log)
- [x] Router registered in `app.py`
- [x] All 19 unit tests pass
