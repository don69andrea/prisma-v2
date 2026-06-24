---
phase: "07"
plan: "02"
subsystem: "frontend/lib/api"
tags: [typescript, api-client, vitest, crypto-dashboard]
dependency_graph:
  requires: ["07-01"]
  provides: ["crypto-signals.ts", "agent-audit.ts", "ohlcv.ts"]
  affects: ["frontend/lib/api/"]
tech_stack:
  added: []
  patterns: ["apiFetch<T> typed wrapper", "TypeScript discriminated unions for backend Pydantic mirrors"]
key_files:
  created:
    - frontend/lib/api/crypto-signals.ts
    - frontend/lib/api/agent-audit.ts
    - frontend/lib/api/ohlcv.ts
    - frontend/lib/api/__tests__/crypto-signals.test.ts
  modified: []
decisions:
  - "Used `type` imports in test file to prevent any accidental runtime import side effects"
  - "Included all optional agent sub-views as `?:` fields in AgentRunDetail matching backend schema"
metrics:
  duration: "~10 min"
  completed: "2026-06-24"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 07 Plan 02: Frontend TypeScript API Clients Summary

## One-liner

Fully-typed TypeScript API clients for all 9 crypto dashboard endpoints using `apiFetch<T>`, mirroring backend Pydantic schemas with no `any` types.

## What Was Built

### Task 1 — crypto-signals.ts (`fd3bc2e`)
- Types: `CryptoAction`, `SignalVector`, `BacktestReport`, `PortfolioCoinStats`, `PortfolioBacktestReport`, `MetaLabelReport`, `TradeSignal`
- Fetchers: `listSignals`, `getSignal`, `getBacktest`, `getPortfolioBacktest`, `getMetaLabel`, `getAgentSignal`
- Covers: `/api/v1/signals`, `/api/v1/backtest/*`, `/api/v1/agent-signal/*`

### Task 2 — agent-audit.ts + ohlcv.ts (`a812cba`)
- Types: `AgentRunDetail` (with 7 optional sub-views), `AgentAuditResponse`, `HitlConfirmRequest`, `HitlConfirmResponse`, `OHLCVBar`, `OHLCVResponse`
- Fetchers: `getAgentAudit`, `confirmHitl` (POST with JSON body), `getOHLCV`
- Covers: `/api/v1/crypto/{coin}/agent-audit`, `/api/v1/crypto/{coin}/ohlcv`, `/api/v1/crypto/{coin}/confirm`

### Task 3 — Vitest type-guard tests (`8eca386`)
- 8 tests across all new types confirming shape contracts
- Verified: 8/8 pass (run via main repo node_modules due to worktree isolation)

## Deviations from Plan

**1. [Rule 3 - Blocking] Vitest run path adjustment**
- **Found during:** Task 3 verification
- **Issue:** `npx vitest run` inside the git worktree fails because `node_modules` are not installed there. `vitest/config` module not found.
- **Fix:** Temporarily copied new source files + test to main repo frontend to run vitest, confirmed 8/8 pass, then removed temp copies. All files remain committed only in the worktree.
- **Files modified:** None (temp-only, cleaned up)

## Self-Check

- [x] `crypto-signals.ts` exports 6 fetch functions + 6 TypeScript types
- [x] `agent-audit.ts` exports `getAgentAudit` + `confirmHitl` + 4 types
- [x] `ohlcv.ts` exports `getOHLCV` + 2 types
- [x] No `any` or unexplained `unknown` types anywhere
- [x] Vitest type tests pass: 8/8
- [x] All imports from `./client` use `apiFetch<T>()`
- [x] `confirmHitl` correctly passes `method: 'POST'` and `Content-Type: application/json`

## Self-Check: PASSED

All 3 files created, all 3 commits verified, 8/8 tests passing.
