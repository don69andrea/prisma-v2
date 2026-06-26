---
phase: 02-v4-2-meta-labeling-planned
plan: "01"
subsystem: signals/meta-labeling
tags: [meta-labeling, tdd, triple-barrier, trend-scan, features, wave-a]
status: complete

dependency_graph:
  requires:
    - backend/application/signals/indicators.py (atr, rsi, macd)
    - backend/application/backtest/guards.py (assert_no_lookahead)
  provides:
    - backend/application/signals/meta_label.py
    - backend/tests/unit/application/test_meta_label.py
  affects:
    - Wave B (classifier) — consumes triple_barrier_labels, trend_scan_labels, build_meta_features

tech_stack:
  added: [scipy.stats.linregress]
  patterns:
    - TDD Red-Green cycle with separate commits
    - Lazy import for scipy (mirrors vol_forecast LightGBM pattern)
    - shift(1) enforced on all feature columns before return
    - Perfectly-linear t-stat guard (stderr=0 → sign(slope)*1e9)

key_files:
  created:
    - backend/application/signals/meta_label.py
    - backend/tests/unit/application/test_meta_label.py
  modified: []

decisions:
  - Triple-Barrier uses indicators.atr (Wilder RMA, window=20) — consistent with codebase ATR
  - trend_scan handles perfectly-linear series (stderr=0) by treating as infinite t-stat signal
  - build_meta_features returns exactly 10 columns — all shift(1); onchain_health defaults 0.5
  - scipy.stats.linregress imported lazily inside trend_scan_labels function

metrics:
  duration: "~15 minutes"
  completed: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 02 Plan 01: Meta-Label Wave A — Labels + Features Summary

**One-liner:** Triple-Barrier (ATR-based) + Trend-Scan (linregress t-stat) labels with 10-column shift(1)-safe feature matrix, TDD red-green cycle complete.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED — failing label + feature tests (ML-01..ML-04) | d6db8da | test_meta_label.py (272 lines, 4 tests) |
| 2 | GREEN — implement meta_label.py | ccdad47 | meta_label.py (252 lines, 3 functions) |

## Artifacts Produced

### `backend/application/signals/meta_label.py`
- `triple_barrier_labels(close, high, low, atr_window=20, upper_mult=2.0, lower_mult=1.0, horizon=5) -> pd.Series[int]`
- `trend_scan_labels(close, min_window=3, max_window=10, t_stat_threshold=1.5) -> pd.Series[int]`
- `build_meta_features(df: pd.DataFrame) -> pd.DataFrame` — exactly 10 columns, all shift(1)

### `backend/tests/unit/application/test_meta_label.py`
- `test_triple_barrier_labels_synthetic` (ML-01)
- `test_trend_scan_labels_direction` (ML-02)
- `test_meta_features_no_lookahead` (ML-03)
- `test_label_horizon_isolation` (ML-04)

## Verification Results

```
4 passed, 2 warnings in 0.28s
ruff: All checks passed
mypy: Success: no issues found
```

The 2 RuntimeWarnings (`invalid value encountered in divide`) originate from numpy's
pearson correlation in `assert_no_lookahead` when a constant feature column (e.g.
`onchain_health=0.5`) has zero stddev. This is benign — guards.py skips columns with
fewer than 2 clean data points, and a constant column correctly has |corr|=NaN (not > 0.999),
so no LookAheadError is raised.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED  | d6db8da `test(meta-label): add RED label + feature tests (ML-01..ML-04)` | PASSED |
| GREEN | ccdad47 `feat(meta-label): implement triple-barrier + trend-scan labels + features` | PASSED |

RED commit precedes GREEN commit — TDD order satisfied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] trend_scan_labels: perfectly-linear series produces stderr=0**
- **Found during:** Task 2 GREEN run (test_trend_scan_labels_direction FAILED)
- **Issue:** Synthetic `_rising_close(step=5.0)` is a perfectly-linear series. `scipy.stats.linregress` returns `stderr=0` for a perfect fit. The original implementation skipped these (no signal), producing all-zero labels even for a strong +5/day trend.
- **Fix:** When `stderr==0 and slope!=0`, use surrogate t-stat = `sign(slope) * 1e9` (effectively infinite). This correctly labels perfectly-linear forward windows as strong trend signals.
- **Files modified:** `backend/application/signals/meta_label.py`
- **Commit:** ccdad47

**2. [Rule 1 - Bug] mypy: unused `type: ignore[attr-defined]` on linregress result attributes**
- **Found during:** Task 2 mypy check
- **Issue:** Newer scipy has proper type stubs; `result.stderr` and `result.slope` are typed, so the `# type: ignore[attr-defined]` comments were flagged as unused.
- **Fix:** Removed the redundant type-ignore comments.
- **Files modified:** `backend/application/signals/meta_label.py`
- **Commit:** ccdad47 (same commit, fix applied before commit)

## Known Stubs

None — all 10 feature columns are wired to real indicator computations or passthrough from df.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. Look-Ahead mitigation (T-02-01) fully implemented via shift(1) + ML-03 assert_no_lookahead test. Boundary guard (T-02-02) implemented via `min(i+horizon+1, n)` + ML-04 isolation test.

## Self-Check

- [x] `backend/application/signals/meta_label.py` exists
- [x] `backend/tests/unit/application/test_meta_label.py` exists
- [x] RED commit d6db8da verified in git log
- [x] GREEN commit ccdad47 verified in git log
- [x] 4/4 tests pass
- [x] ruff clean
- [x] mypy clean

## Self-Check: PASSED
