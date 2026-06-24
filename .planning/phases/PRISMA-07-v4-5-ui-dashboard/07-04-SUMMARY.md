---
phase: "07"
plan: "04"
subsystem: "frontend/components/crypto"
tags: [charts, hitl, equity-curve, candlestick, wissenschaftliche-ehrlichkeit, recharts]
dependency_graph:
  requires: []
  provides:
    - CryptoEquityChart
    - CandlestickChart
    - HitlDialog
  affects:
    - frontend/components/crypto/
key_files:
  created:
    - frontend/components/crypto/CryptoEquityChart.tsx
    - frontend/components/crypto/CandlestickChart.tsx
    - frontend/components/crypto/HitlDialog.tsx
    - frontend/components/crypto/__tests__/HitlDialog.test.tsx
  modified: []
decisions:
  - "CandlestickChart: typed CandleBodyShape component instead of raw `shape` prop with any — cleaner than inline any"
  - "HitlDialog: added SELL annotation (SELL = Exposure 0, kein Shorting) per AGENTS.md Iron Rule"
  - "HitlDialog: added 4th test verifying 'kein Handel wird ausgelöst' text is present"
  - "Tests run from main repo frontend/ (worktree has no node_modules) — verified 4/4 pass"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-24"
  tasks_completed: 4
  files_created: 4
---

# Phase 7 Plan 04: UI Components Set B (Charts + HITL Dialog) Summary

## One-Liner

Recharts-basierte Chart-Komponenten (Equity-Kurve + OHLCV-Approximation) und HitlDialog mit Pflicht-Disclosure "kein Handel wird ausgelöst" und Wissenschaftliche-Ehrlichkeit-Caveats.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | CryptoEquityChart — equity curve + caveats | 198838b | CryptoEquityChart.tsx |
| 2 | CandlestickChart — OHLCV + MA/Bollinger | 529ed0e | CandlestickChart.tsx |
| 3 | HitlDialog — HITL gate, no auto-trade | e38705c | HitlDialog.tsx |
| 4 | HitlDialog unit tests (4 tests) | 97e1b39 | __tests__/HitlDialog.test.tsx |

## Test Results

```
✓ components/crypto/__tests__/HitlDialog.test.tsx  (4 tests) 95ms
  Test Files  1 passed (1)
       Tests  4 passed (4)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added 'kein Handel wird ausgelöst' test**
- Added 4th test case to verify the mandatory Iron Rule disclosure text appears in the rendered dialog.

**2. [Rule 2 - Missing critical functionality] Added SELL Iron Rule annotation**
- HitlDialog now shows explicit note when action=SELL: "SELL bedeutet: Exposure auf 0 reduzieren (kein Leerverkauf / kein Shorting)" per AGENTS.md Iron Rule.

**3. [Rule 1 - Bug] CandlestickChart: typed shape prop**
- Plan showed `shape={(props: any) => ...}` inline. Extracted to typed `CandleBodyShape` component to avoid unchecked any (plan notes one any is acceptable, but a typed component is cleaner).

## Known Stubs

None — all components use real props, no hardcoded empty values that reach UI rendering.

## Threat Flags

None — components are pure UI, no network endpoints or auth paths introduced.

## Self-Check: PASSED

- [x] CryptoEquityChart.tsx exists at frontend/components/crypto/
- [x] CandlestickChart.tsx exists at frontend/components/crypto/
- [x] HitlDialog.tsx exists at frontend/components/crypto/
- [x] __tests__/HitlDialog.test.tsx exists
- [x] Commits 198838b, 529ed0e, e38705c, 97e1b39 verified in git log
- [x] Amber caveats box: regime-dependency, cost >=0.5%, backtest!=live, paper-trading
- [x] "kein Handel wird ausgelöst" present in HitlDialog
- [x] SELL annotation: kein Shorting/Leerverkauf
- [x] 4/4 tests pass
