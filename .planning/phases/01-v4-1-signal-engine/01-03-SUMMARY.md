---
phase: 1
plan: 03
subsystem: signals
tags: [indicators, consensus, tdd, technical-analysis]
dependency_graph:
  requires: [01-01-PLAN.md, 01-02-PLAN.md]
  provides:
    - backend/application/signals/indicators.py
    - backend/application/signals/consensus.py
  affects: []
tech_stack:
  added:
    - ta>=0.11.0 (dev only, cross-validation reference)
  patterns:
    - Pure vectorized pandas/numpy functions (no loops except ATR Wilder smoothing)
    - TDD Red-Green cycle with ta-library cross-validation (delta < 1e-6)
    - Weighted consensus vote with configurable threshold
key_files:
  created:
    - backend/application/signals/__init__.py
    - backend/application/signals/indicators.py
    - backend/application/signals/consensus.py
    - backend/tests/unit/application/test_indicators.py
    - backend/tests/unit/application/test_consensus.py
  modified:
    - pyproject.toml (ta>=0.11.0 added to dev extras)
    - uv.lock
decisions:
  - "ATR uses iterative Wilder smoothing (loop) to exactly match ta reference; vectorized RMA not feasible for delta<1e-6 target"
  - "RSI uses EWM alpha=1/window, adjust=False — Wilder smoothing as per ta implementation"
  - "Bollinger Bands use ddof=0 (population std) matching ta reference"
  - "consensus_vote ignores cfg columns absent from df and df columns absent from cfg — graceful degradation"
  - "ta library added as dev-only dep (not prod) since implementation uses raw pandas"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-21"
  tasks_completed: 2
  files_created: 5
  files_modified: 2
---

# Phase 1 Plan 03: Signals — Indicators and Consensus Voting Summary

**One-liner:** Vectorized technical indicators (sma/ema/macd/rsi/bollinger/atr) with ta-library cross-validation (delta < 1e-6) plus 2-of-3 weighted consensus voting, test-first.

## What Was Built

### T01 — TEST-FIRST: Indicators

**RED commit** `a3782e8`: 8 failing tests in `test_indicators.py` covering SMA, EMA, RSI, MACD (line/signal/hist separately), Bollinger Bands (upper/mid/lower), and ATR vs OHLC input.

**GREEN commit** `8605121`: `backend/application/signals/indicators.py` with 6 pure functions:

| Function | Signature | Notes |
|---|---|---|
| `sma` | `(close, window) -> Series` | `rolling(window, min_periods=window).mean()` |
| `ema` | `(close, window) -> Series` | `ewm(span=window, min_periods=window, adjust=False)` |
| `rsi` | `(close, window=14) -> Series` | Wilder EWM alpha=1/window |
| `macd` | `(close, fast=12, slow=26, signal=9) -> tuple[Series,Series,Series]` | EMA fast/slow diff |
| `bollinger` | `(close, window=20, std=2.0) -> tuple[Series,Series,Series]` | ddof=0 (population std) |
| `atr` | `(high, low, close, window=14) -> Series` | Iterative Wilder RMA loop |

All indicators match the ta library reference within **delta < 1e-6**.

### T02 — TEST-FIRST: 2-of-3 Consensus Vote

**RED commit** `a3782e8`: 8 failing tests in `test_consensus.py` with full truth table (all 8 binary combinations) plus weighted/threshold/edge-case tests.

**GREEN commit** `8605121`: `backend/application/signals/consensus.py`:

```
weighted_sum = sum(df[col] * weight for col, weight in weights.items() if col in df.columns)
normalised   = weighted_sum / total_weight
result       = (normalised >= threshold).astype(int)
```

Default cfg: `{ma_signal: 1.0, macd_signal: 1.0, rsi_signal: 1.0, threshold: 0.5}` — implements exactly 2-of-3 majority rule.

## Test Results

```
16 passed in 0.05s
  test_sma_matches_ta        PASSED (delta=0.0)
  test_ema_matches_ta        PASSED (delta=0.0)
  test_rsi_matches_ta        PASSED (delta < 1e-15)
  test_macd_matches_ta       PASSED (all 3 components)
  test_bollinger_matches_ta  PASSED (all 3 bands)
  test_atr_requires_ohlc     PASSED (delta < 1e-15)
  test_sma_returns_series    PASSED
  test_macd_returns_three_series PASSED
  test_consensus_full_truth_table        PASSED (all 8 combinations)
  test_consensus_returns_series          PASSED
  test_consensus_series_dtype_is_int     PASSED
  test_consensus_weighted_mode           PASSED
  test_consensus_custom_threshold        PASSED
  test_consensus_ignores_unknown_columns PASSED
  test_consensus_no_matching_columns_returns_zeros PASSED
  test_consensus_default_cfg_is_2_of_3   PASSED
```

## TDD Gate Compliance

- RED gate: `test(01-03)` commit `a3782e8` — all 16 tests failed before implementation
- GREEN gate: `feat(01-03)` commit `8605121` — all 16 tests pass
- REFACTOR: no structural refactoring needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] ta library not in pyproject.toml**
- **Found during:** T01 setup
- **Issue:** `ta` was listed as available in constraints but absent from `pyproject.toml`; `uv run pytest` collected tests with Python 3.13 (system) instead of venv Python 3.12
- **Fix:** Added `ta>=0.11.0` to `[project.optional-dependencies].dev`, ran `uv sync --extra dev`; removed duplicate `[dependency-groups]` block created by `uv add ta`
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Impact:** Tests now run correctly under Python 3.12 venv

**2. [Rule 3 - Blocker] pytest absent from uv venv**
- **Found during:** T01 RED phase
- **Issue:** `uv run pytest` resolved to `/opt/homebrew/bin/pytest` (system Python 3.13) instead of the project venv; `ta` module not found under Python 3.13
- **Fix:** `uv add --dev pytest pytest-asyncio` to populate venv; then reverted duplicate entries after cleaning up `pyproject.toml`
- **Files modified:** `pyproject.toml`, `uv.lock`

### Architectural Notes

- ATR uses a `for` loop (intentional): vectorized Wilder RMA cannot match the ta reference within 1e-6 due to seed value computation (`atr[window-1] = tr[:window].mean()`); the iterative approach is the only correct implementation.

## Known Stubs

None — all functions fully implemented and verified.

## Threat Flags

None — no network endpoints, auth paths, or trust-boundary changes introduced.

## Self-Check

- [ ] Files exist
- [ ] Commits exist

## Self-Check: PASSED
