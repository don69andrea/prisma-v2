---
phase: 02-v4-2-meta-labeling-planned
plan: "03"
subsystem: backtest-integration
tags: [meta-labeling, walkforward, pydantic, tdd, ML-07, ML-08]
dependency_graph:
  requires: [02-02]
  provides: [meta_filter-param, MetaLabelReport-schema]
  affects: [walkforward.py, schemas/signals.py]
tech_stack:
  added: []
  patterns: [TDD red-green, expanding-window meta-masking, Pydantic schema extension]
key_files:
  created: []
  modified:
    - backend/application/backtest/walkforward.py
    - backend/interfaces/rest/schemas/signals.py
    - backend/tests/unit/application/test_walkforward.py
decisions:
  - meta_filter defaults to None so all existing callers see zero behaviour change (ML-08)
  - masking applied after shift(1) so look-ahead prevention is preserved
  - MetaLabelReport uses Literal constraints for label_method, classifier, finding fields
metrics:
  duration: "~5 minutes"
  completed: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
status: complete
---

# Phase 2 Plan 03: Backtest Integration (meta_filter + MetaLabelReport) Summary

**One-liner:** Optional `meta_filter: pd.Series | None = None` on both walk-forward entry points
masks positions where meta_label==0; `MetaLabelReport` Pydantic schema carries the full
always-trade vs. meta-filtered comparison report.

## Tasks Completed

| # | Task | Commit | Type |
|---|------|--------|------|
| 1 | RED — meta_filter backward-compat + baseline tests (ML-07, ML-08) | f29b13a | test |
| 2 | GREEN — add meta_filter param + MetaLabelReport schema | 270d0f3 | feat |

## What Was Built

### walkforward.py — meta_filter parameter

Both `run_walkforward()` and `run_walkforward_with_details()` now accept an optional last
keyword argument:

```python
meta_filter: pd.Series | None = None
```

When `meta_filter is not None`, positions are masked immediately after the look-ahead shift:

```python
meta_aligned = meta_filter.reindex(close.index).fillna(0.0)
position = position * meta_aligned
```

Everything downstream (turnover, costs, baseline, metrics) recomputes from the masked position,
so always-trade and meta-filtered runs share the same OOS date index (ML-07).

### schemas/signals.py — MetaLabelReport

New Pydantic model with all 15 fields per CONTEXT.md:

- `coin`, `label_method`, `classifier`, `n_folds`
- `oos_precision`, `oos_recall`
- `always_trade_sharpe`, `always_trade_calmar`
- `meta_filtered_sharpe`, `meta_filtered_calmar`
- `n_trades_always`, `n_trades_filtered`
- `beats_baseline`, `finding`, `finding_reason`

`finding` is `Literal["positive","secondary_pass","negative"]`. Literal constraints on
`label_method` and `classifier` enforce the contract at schema level.

### Tests added (test_walkforward.py)

- `test_meta_filter_backward_compat` (ML-08): no-arg vs all-ones filter → metrics match at atol=1e-12
- `test_meta_filter_masks_positions`: 50% zero-block reduces avg_exposure and n_trades
- `test_baseline_same_oos_period` (ML-07): always-trade and filtered net_returns share identical index

## Test Results

```
18 passed, 2 warnings in 0.42s
```

All 18 tests green (9 pre-existing walkforward + 6 meta_label + 3 new meta_filter).

## Ruff Check

```
All checks passed!
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Quoted type annotations caused ruff UP037 warnings**
- **Found during:** Task 2 (ruff check)
- **Issue:** `"pd.Series | None"` quoted form is redundant with `from __future__ import annotations`
- **Fix:** Removed quotes — `pd.Series | None` directly
- **Files modified:** `backend/application/backtest/walkforward.py`
- **Commit:** 270d0f3 (fixed inline before final commit)

None of the planned logic was changed. The plan executed exactly as written otherwise.

## TDD Gate Compliance

- RED gate commit: `f29b13a` (`test(walkforward): add RED meta_filter + baseline tests`)
- GREEN gate commit: `270d0f3` (`feat(walkforward): add optional meta_filter + MetaLabelReport schema`)
- Both gates present and in correct order.

## Known Stubs

None — all fields of MetaLabelReport are typed with real constraints; no placeholder values
flow to UI (no UI this phase).

## Threat Flags

No new network endpoints or auth paths introduced. MetaLabelReport schema is output-only
(used as response_model for a future Wave D endpoint, not yet wired). No new trust boundaries.

## Self-Check: PASSED

- [x] `backend/application/backtest/walkforward.py` — modified, meta_filter present
- [x] `backend/interfaces/rest/schemas/signals.py` — MetaLabelReport present and importable
- [x] `backend/tests/unit/application/test_walkforward.py` — 3 new tests present
- [x] Commit f29b13a exists (RED)
- [x] Commit 270d0f3 exists (GREEN)
- [x] 18 tests pass, 0 failures
- [x] ruff check: All checks passed
