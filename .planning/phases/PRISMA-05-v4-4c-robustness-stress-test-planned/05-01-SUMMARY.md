---
phase: 05-v4-4c-robustness-stress-test
plan: 01
subsystem: scripts
tags: [robustness, stress-test, backtest, consensus, yfinance, rich]
dependency_graph:
  requires:
    - backend/application/backtest/walkforward.py
    - backend/application/signals/consensus.py
    - backend/application/signals/indicators.py
    - backend/application/signals/sizing.py
  provides:
    - scripts/robustness_check.py
  affects: []
tech_stack:
  added: []
  patterns:
    - standalone sync harness (no asyncio, no DB)
    - yfinance direct download with UTC tz_localize
    - Rich console tables for structured CLI output
    - dataclasses(frozen=True) for immutable result records
    - shift(1)-before-consensus look-ahead guard pattern
key_files:
  created:
    - scripts/robustness_check.py
  modified: []
decisions:
  - "rolling(21) vol approximation used instead of fit_walkforward per D-10 (speed vs accuracy trade-off for standalone harness)"
  - "shift(1) applied to all 3 binary signals (ma, rsi, macd) before consensus_vote — no look-ahead (D-09)"
  - "_bah_metrics() returns 3-tuple (sharpe, calmar, max_dd) — all callers unpack all three"
  - "Bear-2018 regime: SOL/AVAX/DOT/MATIC hardcoded as not-listed (set _NOT_LISTED_2018)"
  - "MATIC-USD download end capped at 2025-03-24 with note field in RegimeResult"
metrics:
  duration: "~15 min"
  completed: "2026-06-23"
  tasks_completed: 1
  files_created: 1
---

# Phase 5 Plan 01: Robustness Harness Summary

**One-liner:** Standalone 4-dimension stress harness — consensus_vote() real, rolling(21) vol, bah_max_dd per regime, shift(1) look-ahead guard, Rich tables, no DB/asyncio.

## What Was Built

`scripts/robustness_check.py` (793 lines) — a fully standalone, synchronous robustness harness implementing 4 stress-test dimensions against the V4-1 edge. Importable for testing. Returns a dict from `main()`.

### Structure

| Component | Description |
|-----------|-------------|
| `build_signals(close, ma_window=100)` | SMA/RSI/MACD signals with shift(1) before `consensus_vote()`, rolling(21) vol sizing |
| `_bah_metrics(close)` | Buy&Hold baseline via walk-forward engine; returns `(sharpe, calmar, max_dd)` |
| `_download(coin, start, end)` | yfinance download with UTC tz_localize; returns None on empty |
| `run_cost_sensitivity()` | Dim 1: BTC/ETH at costs 0.001/0.002/0.005 → list[CostResult] |
| `run_regime_splits()` | Dim 2: 10 coins × 4 regimes; OOS slice per regime; bah_max_dd per RegimeResult |
| `run_universe()` | Dim 3: all 10 coins; <315 rows → insufficient dict |
| `run_parameter_stability()` | Dim 4: BTC/ETH × SMA [50,75,100,150,200]; is_default=True for 100 |
| `print_*_table()` | 4 Rich console tables, one per dimension |
| `main()` | Prints _APPROX_NOTE, runs all 4 dims, returns dict with 4 keys |

### Key Implementation Requirements Met

- `_APPROX_NOTE` printed at top of `main()` via `console.print()` (honest labeling)
- `RegimeResult.bah_max_dd: float` field included (MaxDD B&H sliced to regime window)
- `_bah_metrics()` returns 3-tuple `(bah_sharpe, bah_calmar, bah_max_dd)`
- `run_regime_splits()` computes `bah_details` via `run_walkforward_with_details(prices_df, pd.Series(1.0, ...), costs=0.0001)` and slices to regime window
- `print_regime_table()` columns: Coin / Regime / Sharpe(Strat) / Calmar(Strat) / MaxDD(Strat) / MaxDD(B&H) / OOS-Rows / Status
- `build_signals()` uses `consensus_vote()` from `backend.application.signals.consensus` (not inline logic)
- FORBIDDEN patterns (asyncio, DB imports, signal_service, fit_walkforward) absent from implementation (2 grep hits are in string literals only)

## Verification Results

```
build_signals OK, len= 600
IMPORT OK
```

All grep checks passed:
- `shift(1)` appears 5 times (lines 202, 216, 217, 218, 219) — all before `consensus_vote` call at line 226
- `consensus_vote` imported at line 35 and called at line 226
- `asyncio` / `signal_service` / `fit_walkforward` — only in string literals (comments/constants), zero actual imports or calls

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All functions are fully implemented. The harness is network-dependent (yfinance) so results depend on data availability at runtime; `insufficient` / `download_failed` dicts are the designed fallback.

## Threat Flags

No new security-relevant surface introduced. The script is read-only analysis, no API keys, no DB writes, no new network endpoints. yfinance via `auto_adjust=True` only.

## Self-Check

- [x] `scripts/robustness_check.py` exists (793 lines, >= 300 minimum)
- [x] Commit `729152d` exists: `feat(v4-4c): robustness harness...`
- [x] All 4 `run_*` functions present with correct signatures
- [x] `main()` returns `dict` with 4 keys
- [x] `build_signals()` uses `consensus_vote()` from backend module
- [x] `RegimeResult.bah_max_dd` field present
- [x] `_bah_metrics()` returns 3-tuple
- [x] `_APPROX_NOTE` defined and printed at top of `main()`
- [x] No asyncio, no DB imports, no signal_service, no fit_walkforward calls

## Self-Check: PASSED
