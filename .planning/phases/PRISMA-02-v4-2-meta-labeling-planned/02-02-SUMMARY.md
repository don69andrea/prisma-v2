---
phase: 02-v4-2-meta-labeling-planned
plan: "02"
subsystem: meta-labeling-classifier
status: complete
tags: [meta-labeling, classifier, walk-forward, logreg, lgbm, tdd]
dependency_graph:
  requires: [02-01]
  provides: [fit_meta_classifier, predict_meta_label, _walkforward_meta_cv]
  affects: [backend/application/signals/meta_label.py]
tech_stack:
  added: []
  patterns: [expanding-window-walk-forward, embargo-no-snooping, logreg-primary-lgbm-fallback]
key_files:
  created: []
  modified:
    - backend/application/signals/meta_label.py
    - backend/tests/unit/application/test_meta_label.py
decisions:
  - LogisticRegression primary with class_weight=balanced to handle crypto class imbalance
  - 5-day embargo enforced via test_start=start+embargo in _walkforward_meta_cv
  - dict[str, Any] return type for all classifier functions (mypy strict compliant)
  - sklearn.base.BaseEstimator.fit called via isinstance-guard pattern (avoids B009 ruff)
metrics:
  duration: "~15 min"
  completed: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 02 Plan 02: Meta-Classifier Walk-Forward Summary

**One-liner:** LogisticRegression-primary meta-classifier with 5-day embargo expanding walk-forward (min_train=252, step=21) achieving OOS precision >50% on learnable synthetic data.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED — write failing classifier walk-forward tests (ML-05, ML-06) | 78ddc42 | backend/tests/unit/application/test_meta_label.py |
| 2 | GREEN — implement fit_meta_classifier, predict_meta_label, _walkforward_meta_cv | c4c20b3 | backend/application/signals/meta_label.py |

## Functions Introduced

### `fit_meta_classifier(X, y, model='logreg') -> dict[str, Any]`
- Lazy-imports LogisticRegression or LGBMClassifier based on `model` parameter
- LogisticRegression: C=1.0, max_iter=1000, class_weight='balanced', random_state=42
- LGBMClassifier: n_estimators=100, max_depth=4, learning_rate=0.05, n_jobs=1, verbose=-1
- Returns {model, model_type, feature_cols}

### `_walkforward_meta_cv(X, y, min_train=252, step=21, embargo=5, model_type='logreg') -> dict[str, Any]`
- Expanding window: train=data[:start], test=data[start+embargo : start+embargo+step]
- Embargo gap is the no-snooping guarantee (T-02-03 threat mitigation)
- Skips folds where train has <2 classes
- Per-fold output: precision, recall, f1, n_trades_taken, n_trades_skipped, train_end_idx, test_start_idx
- Uses sklearn.metrics precision_score/recall_score/f1_score with zero_division=0

### `predict_meta_label(X, y, min_train=252, step=21, embargo=5, model='logreg') -> dict[str, Any]`
- Runs _walkforward_meta_cv and aggregates mean precision/recall/f1
- Refits final model on all data for production scoring
- n_folds < 10 → finding='negative', finding_reason='insufficient_oos_folds' (T-02-04 mitigation)
- Returns finding='positive' if mean_precision > 0.50

## Test Results

```
6 passed, 2 warnings in 0.35s

test_triple_barrier_labels_synthetic  PASSED  (ML-01)
test_trend_scan_labels_direction      PASSED  (ML-02)
test_meta_features_no_lookahead       PASSED  (ML-03)
test_label_horizon_isolation          PASSED  (ML-04)
test_classifier_oos_above_random      PASSED  (ML-05)
test_no_snooping                      PASSED  (ML-06)
```

## Lint / Type Check

- `ruff check backend/application/signals/meta_label.py` — All checks passed
- `mypy backend/application/signals/meta_label.py --ignore-missing-imports` — Success: no issues found

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] getattr pattern replaced with isinstance-guard**
- **Found during:** Task 2 (ruff check)
- **Issue:** Initial `getattr(clf, "fit")` pattern triggered ruff B009 (do not call getattr with constant attribute)
- **Fix:** Used `isinstance(clf, BaseEstimator)` guard then called `.fit()` directly; updated return type annotations to `dict[str, Any]` to avoid mypy strict false positives
- **Files modified:** backend/application/signals/meta_label.py
- **Commit:** c4c20b3

None other — plan executed as written.

## TDD Gate Compliance

- RED gate: `test(meta-label): add RED classifier walk-forward tests (ML-05, ML-06)` — commit 78ddc42
- GREEN gate: `feat(meta-label): add meta-classifier walk-forward (logreg + lgbm fallback)` — commit c4c20b3
- Both gates present in git log in correct order.

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-02-03 (label leakage / no embargo) | test_start = start + embargo in _walkforward_meta_cv; ML-06 invariant test blocks merge |
| T-02-04 (unreliable metrics from too-few folds) | n_folds < 10 check; finding='negative' with reason instead of fabricated numbers |

## Self-Check: PASSED

- backend/application/signals/meta_label.py — exists, contains `def fit_meta_classifier`
- backend/tests/unit/application/test_meta_label.py — exists, contains `test_classifier_oos_above_random`
- Commit 78ddc42 — RED tests
- Commit c4c20b3 — GREEN implementation
- All 6 tests pass
- ruff and mypy clean
