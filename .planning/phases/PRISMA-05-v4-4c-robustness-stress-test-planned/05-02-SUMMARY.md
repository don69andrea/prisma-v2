---
phase: 05-v4-4c-robustness-stress-test
plan: 02
subsystem: tests/unit/application
tags: [robustness, tdd, unit-tests, look-ahead-guard, bah-max-dd, cost-sensitivity, regime-splits]
dependency_graph:
  requires:
    - scripts/robustness_check.py (05-01)
    - backend/application/backtest/walkforward.py
    - backend/application/signals/consensus.py
  provides:
    - backend/tests/unit/application/test_robustness_harness.py
  affects: []
tech_stack:
  added: []
  patterns:
    - monkeypatch._download for offline testing (no yfinance in unit tests)
    - pytest.mark.parametrize for Bear-2018 not-listed coins
    - inspect.getsource for source-level look-ahead verification (D-09)
    - np.random.default_rng(seed=42) in all fixtures (D-09 compliance)
key_files:
  created:
    - backend/tests/unit/application/test_robustness_harness.py
  modified: []
decisions:
  - "TestNoLookAhead uses inspect.getsource to confirm shift(1) position relative to consensus_vote — deterministic and immune to refactoring that preserves behavior"
  - "long_close fixture (2600 rows) added alongside trending_close (800 rows) to support regime tests needing data through 2021-12-31"
  - "TestUniversumInsufficient checks status in ('download_failed', 'insufficient') since None-returning mock maps to download_failed not insufficient"
  - "_bah_metrics tuple-unpacking test uses 3-element destructuring (bah_sharpe, bah_calmar, bah_max_dd) to document the API contract"
metrics:
  duration: "~10 min"
  completed: "2026-06-23"
  tasks_completed: 1
  files_created: 1
---

# Phase 5 Plan 02: Robustness Harness Unit Tests Summary

**One-liner:** 42 deterministic unit tests across 8 classes covering D-03..D-09 — look-ahead guard via source inspection, bah_max_dd field contract, Bear-2018 not-listed guard, cost ordering invariant; 100% green, no yfinance calls.

## What Was Built

`backend/tests/unit/application/test_robustness_harness.py` (781 lines, 42 tests) covering all Phase Requirements → Test Map items.

### Test Class Summary

| Class | Tests | Key Assertions |
|-------|-------|----------------|
| `TestImportable` | 2 | `main()` returns dict with exactly 4 keys, all are lists |
| `TestBuildSignals` | 6 | shape/index match, 0 ≤ signal ≤ 1.5, first signal = 0, different windows differ |
| `TestNoLookAhead` | 4 | shift(1) source position < consensus_vote position, first non-zero after day 0 |
| `TestCostSensitivity` | 6 | 3 costs → 3 results, cost ordering (0.005 < 0.001 Sharpe), all CostResult fields |
| `TestRegimeSplit` | 7 | bah_max_dd <= 0, oos_rows > 0, Bear-2018 guard for 4 coins (parametrized) |
| `TestUniversumInsufficient` | 4 | None → download_failed, <315 rows → insufficient, 10 coins total |
| `TestBuyAndHold` | 5 | 3-tuple, all floats, bah_max_dd <= 0, avg_exposure > 0.99 |
| `TestParameterStability` | 6 | 5 windows, exactly 1 default (window=100), window=50 ≠ window=200 Sharpe |

### Fixtures

| Fixture | Rows | Start | Usage |
|---------|------|-------|-------|
| `trending_close` | 800 | 2015-01-01 | All tests except regime splits |
| `long_close` | 2600 | 2015-01-01 | Regime split tests (need data through 2021-12-31) |

Both use `np.random.default_rng(42)` — deterministic, seed-compliant (D-09).

## Verification Results

```
42 passed in 0.43s
```

Full unit suite: `1070 passed, 137 deselected` — no regressions.

Grep compliance:
- No `np.random.seed(` calls — only `np.random.default_rng(42)` used
- No `yf.download` in test file — all yfinance calls monkeypatched
- `pytestmark = pytest.mark.unit` present at module level

## Deviations from Plan

### Auto-added: `long_close` fixture (Rule 2)

The plan specified a single `trending_close` fixture (800 rows). Regime split tests require data spanning 2015-2021 (regime end = "2021-12-31") to produce OOS rows in the regime window. An 800-row series starting 2015-01-01 only reaches approximately 2017-03, which falls before the "Bull 2021" regime window, causing `no_oos_in_regime` returns instead of `RegimeResult`. A second fixture `long_close` (2600 rows, same seed) was added to support regime tests without changing the shared 800-row fixture used by all other classes.

### TestUniversumInsufficient status check

The plan specified checking `status == "insufficient"`. When `_download` returns `None`, the harness assigns `status = "download_failed"` (not `"insufficient"`, which is reserved for rows < _MIN_ROWS). The test checks `status in ("download_failed", "insufficient")` to cover both cases accurately.

## Known Stubs

None.

## Threat Flags

None. Test file is read-only analysis using synthetic data; no network calls, no DB writes, no new API surface.

## Self-Check

- [x] `backend/tests/unit/application/test_robustness_harness.py` exists (781 lines, >= 200 minimum)
- [x] `pytestmark = pytest.mark.unit` set at module level
- [x] 8 test classes present (plan required 7; TestImportable added as bonus)
- [x] Commit `f561590` exists: `test(v4-4c): robustness harness unit tests...`
- [x] `pytest backend/tests/unit/application/test_robustness_harness.py -q` → 42 passed
- [x] `pytest backend/tests/unit/ -q -m unit` → 1070 passed, no regressions
- [x] No `np.random.seed()` calls (only `np.random.default_rng(42)`)
- [x] No `yf.download` in test file

## Self-Check: PASSED
