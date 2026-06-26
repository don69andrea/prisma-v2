# Phase 2: V4-2 Meta-Labeling — Research

**Researched:** 2026-06-21
**Domain:** Binary meta-classifier (López de Prado Meta-Labeling) — Triple-Barrier + Trend-Scan labels, LogisticRegression primary classifier, strict walk-forward.
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Labeling:** Implement BOTH Triple-Barrier (upper=+2×ATR(20), lower=−1×ATR(20), time=5 days) AND Trend-Scanning (scan 3–10 bars, t-stat > 1.5 threshold). Compare on BTC+ETH; choose higher OOS precision. If Δprecision < 5%, default to Triple-Barrier.

**Classifier:** LogisticRegression (sklearn, L2, max_iter=1000) as primary. LightGBM fallback only if LogReg OOS precision < LightGBM by >5pp AND LogReg precision < 55%. Both wrapped in `fit_meta_classifier(X, y, model='logreg'|'lgbm')`.

**Features:** sub_scores from SignalVector (ma_signal, macd_signal, rsi_signal, consensus_score) + raw indicator values (rsi_value, macd_hist, atr_norm, vol_pred, momentum_rank, onchain_health). All features shift(1) before classifier. Built in `build_meta_features(df) -> pd.DataFrame`.

**Walk-forward:** Expanding window, min_train=252, step=21, embargo=5 days. Min 10 OOS folds required for valid result.

**Baseline:** "Always-trade" = V4-1 consensus without meta filter on the SAME OOS period. Meta-filtered = consensus=1 AND meta_label=1.

**Success:** Primary = both Sharpe AND Calmar better vs always-trade on BTC and/or ETH. Secondary = trade count or max_dd reduced ≥10% without Sharpe/Calmar loss >5%. Negative finding is valid. No parameter tuning until it looks good.

**New module:** `backend/application/signals/meta_label.py`
**Extend:** `backend/application/backtest/walkforward.py` (add optional `meta_filter` param, non-breaking)
**New schema:** MetaLabelReport (Pydantic) in `backend/interfaces/rest/schemas/signals.py`
**New endpoint:** GET /api/v1/signals/meta-label/{coin}

**No-touch list:** consensus.py, vol_forecast.py, sizing.py, factors.py, all SMI services/agents, frontend/

**Build order:** Wave A (Labels+features) → Wave B (Classifier+WF) → Wave C (Backtest integration) → Wave D (API + coverage gate)

### Claude's Discretion

None specified in CONTEXT.md — all significant implementation choices are locked.

### Deferred Ideas (OUT OF SCOPE)

- RandomForest (slower, no advantage over LightGBM if already in deps)
- Any UI / frontend
- Any SMI agent changes
- Parameter tuning to improve results
- Purged cross-validation (use expanding window only, same as V4-1)
</user_constraints>

---

## Summary

Phase 02 builds a binary meta-classifier that filters V4-1 consensus signals: "take this trade now?" The core technical challenge is implementing Triple-Barrier and Trend-Scanning labels correctly without look-ahead — the boundary rule is that label@t uses price data from [t, t+horizon] (forward-looking price path to determine outcome), while features@t use data ≤ t−1 (shift(1) enforced). These two "look-forward" directions are independent: the label looks forward in price to determine the outcome, the feature looks backward in price to construct inputs.

All required dependencies (scikit-learn 1.9.0, lightgbm 4.6.0) are already in pyproject.toml and confirmed installed. The walk-forward pattern from `vol_forecast.py` is a near-exact template for the meta-classifier loop: expanding window with min_train=252, step=21. The key difference is the embargo (5-day gap) between train-end and test-start, which prevents label-leakage from the 5-day triple-barrier horizon bleeding into training.

The cleanest extension of `walkforward.py` is an optional `meta_filter: pd.Series | None = None` parameter that, when provided, masks positions to 0 wherever meta_label=0. This is fully backward-compatible (existing callers pass nothing). `guards.py` currently uses correlation-based look-ahead detection; extending it for meta features means adding a check that meta features at time t are not correlated with future price at t+1 (the same 0.999 threshold works).

**Primary recommendation:** Use `vol_forecast.py`'s `_fit_single_coin()` pattern as the direct template for the meta-classifier walk-forward loop. Copy the lazy LightGBM import pattern. Use `pd.Series.shift(1)` on all features before any train/test split. Apply embargo by slicing `data.iloc[start+embargo : start+step+embargo]` for test windows.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Triple-Barrier labeling | Application (signals) | — | Pure computation on price series; no I/O |
| Trend-Scanning labeling | Application (signals) | — | Pure computation; stateless |
| Feature construction | Application (signals) | — | Aggregates from existing signal layer outputs |
| Meta-classifier walk-forward | Application (signals) | — | Reuses expanding-window pattern from vol_forecast |
| Backtest integration (meta_filter) | Application (backtest) | — | Extension to existing walkforward.py engine |
| MetaLabelReport schema | Interfaces (REST schemas) | — | Pydantic contract for API output |
| REST endpoint | Interfaces (REST routers) | — | Thin router over application service |
| Look-ahead guard extension | Application (backtest) | — | guards.py check for meta features |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-learn | 1.9.0 | LogisticRegression primary classifier | [VERIFIED: pyproject.toml + installed] Already in deps; standard for explainable binary classifiers |
| lightgbm | 4.6.0 | LightGBM fallback classifier | [VERIFIED: pyproject.toml + installed] Already in deps; same pattern as vol_forecast.py |
| pandas | 3.0.3 | Time series alignment, shift, rolling | [VERIFIED: pyproject.toml + installed] Core dependency |
| numpy | 2.2.6 | Numerical ops, t-stat computation | [VERIFIED: pyproject.toml + installed] Core dependency |
| pydantic | >=2.6 | MetaLabelReport schema | [VERIFIED: pyproject.toml] All public interfaces use Pydantic |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy.stats | >=1.13 | linregress for Trend-Scan t-statistic | Computing linear fit t-statistic over forward windows; already in deps |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LogisticRegression | RandomForest | RF is slower, less interpretable; LOCKED OUT by CONTEXT.md |
| Hand-rolled t-stat | scipy.stats.linregress | scipy already in deps, gives t-value directly with correct degrees of freedom |
| mlfinlab Triple-Barrier | Hand-roll from paper | mlfinlab is NOT in deps and would add a large extra dependency. Hand-roll is 30 lines and the formula is exact — PREFERRED |

**Installation:** No new packages required. All dependencies confirmed present.

---

## Package Legitimacy Audit

No new packages are introduced in this phase. All libraries (scikit-learn, lightgbm, pandas, numpy, scipy, pydantic) are already declared in `pyproject.toml` and confirmed installed:

| Package | Registry | Age | Downloads | Verdict | Disposition |
|---------|----------|-----|-----------|---------|-------------|
| scikit-learn | PyPI | ~15 yrs | Very high | OK | Already in deps — approved |
| lightgbm | PyPI | ~8 yrs | Very high | OK | Already in deps — approved |
| scipy | PyPI | ~20 yrs | Very high | OK | Already in deps — approved |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious (SUS):** none

---

## Architecture Patterns

### System Architecture Diagram

```
Price series (OHLCV)
        │
        ▼
┌───────────────────────────────────────────────┐
│  meta_label.py                                │
│                                               │
│  triple_barrier_labels(close, high, low)      │
│    ├─ compute ATR(20) at each t               │
│    ├─ upper = price[t] + 2×ATR[t]            │
│    ├─ lower = price[t] - 1×ATR[t]            │
│    ├─ scan price[t+1..t+5] for first touch   │
│    └─ return Series: +1/−1/0 (time-barrier)  │
│                                               │
│  trend_scan_labels(close)                     │
│    ├─ for each t, scan window 3..10           │
│    ├─ linregress(close[t..t+w]) → t_stat     │
│    ├─ label = sign of t_stat if |t| > 1.5    │
│    └─ return Series: +1/−1                   │
│                                               │
│  build_meta_features(df) → shift(1) all      │
│    ├─ sub_scores from SignalVector            │
│    │   (ma_signal, macd_signal, rsi_signal,  │
│    │    consensus_score)                      │
│    ├─ raw: rsi_value, macd_hist, atr_norm    │
│    ├─ vol_pred (from vol_forecast)           │
│    ├─ momentum_rank (from factors)           │
│    └─ onchain_health (from factors, fill=0.5)│
│                                               │
│  _walkforward_meta_cv(X, y)                  │
│    ├─ expanding: min_train=252, step=21       │
│    ├─ embargo=5 (skip [train_end..+5])       │
│    ├─ fit LogisticRegression on train folds  │
│    ├─ predict on OOS folds                   │
│    └─ collect precision/recall/F1 per fold   │
│                                               │
│  fit_meta_classifier(X, y, model)            │
│  predict_meta_label(X, model_info)           │
└───────────────────────────────────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐    ┌────────────────────────────┐
│ walkforward  │    │   MetaLabelReport (Pydantic)│
│   .py        │    │   oos_precision, recall     │
│              │    │   always_trade_sharpe/calmar│
│ meta_filter= │    │   meta_filtered_sharpe/cal  │
│ pd.Series    │    │   beats_baseline: bool      │
│ masks pos=0  │    │   finding: positive/sec/neg │
│ when label=0 │    └────────────────────────────┘
└──────────────┘             │
        │                    ▼
        │           GET /api/v1/signals/
        │               meta-label/{coin}
        ▼
 BacktestReport (always-trade + meta-filtered)
```

### Recommended Project Structure

```
backend/application/signals/
    meta_label.py               # NEW: labels + classifier + features

backend/application/backtest/
    walkforward.py              # EXTEND: optional meta_filter param

backend/interfaces/rest/
    schemas/signals.py          # EXTEND: MetaLabelReport
    routers/signals.py          # EXTEND: GET /api/v1/signals/meta-label/{coin}

backend/tests/unit/application/
    test_meta_label.py          # NEW: all label + classifier tests
    test_walkforward.py         # EXTEND: meta_filter integration tests
```

### Pattern 1: Triple-Barrier Labeling (hand-rolled, no mlfinlab)

**What:** For each bar t, compute upper/lower/time barriers. Scan forward price path; first barrier touched determines label. +1 = upper hit first, −1 = lower hit first, 0 = time barrier (no strong move).

**When to use:** Primary labeling method. Labels are computed on raw price series, then aligned to the consensus signal dates.

**Point-in-time rule:** Label at t uses `close[t], close[t+1], ..., close[t+horizon]`. Features at t use shifted data (≤ t−1). These are independent axes: the label looks forward in time to determine outcome, features look backward to describe the entry context. There is NO look-ahead contamination as long as features are constructed with `shift(1)`.

**Example:**
```python
# Source: López de Prado, "Advances in Financial Machine Learning", Ch. 3
def triple_barrier_labels(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    atr_window: int = 20,
    upper_mult: float = 2.0,
    lower_mult: float = 1.0,
    horizon: int = 5,
) -> pd.Series:
    """
    Returns pd.Series with values: +1 (upper), -1 (lower), 0 (time-barrier).
    Label at index t uses prices [t, t+horizon] — forward-looking by design.
    Features passed to classifier must be shift(1) to avoid contamination.
    """
    from backend.application.signals.indicators import atr as compute_atr
    atr_vals = compute_atr(high, low, close, window=atr_window)

    labels: dict = {}
    for i, t in enumerate(close.index):
        atr_t = atr_vals.iloc[i]
        if atr_t == 0 or pd.isna(atr_t):
            labels[t] = 0
            continue
        price_t = close.iloc[i]
        upper = price_t + upper_mult * atr_t
        lower = price_t - lower_mult * atr_t
        # Forward window: price[t+1..t+horizon]
        end_idx = min(i + horizon + 1, len(close))
        forward = close.iloc[i + 1 : end_idx]
        label = 0  # default: time barrier
        for fp in forward:
            if fp >= upper:
                label = 1
                break
            if fp <= lower:
                label = -1
                break
        labels[t] = label
    return pd.Series(labels, dtype=int)
```

### Pattern 2: Trend-Scanning Labels (hand-rolled)

**What:** For each bar t, scan forward windows of 3 to 10 bars. Fit a linear regression; if the absolute t-statistic > 1.5, assign label = sign of slope. Use the window with maximum absolute t-stat.

**Example:**
```python
# Source: López de Prado, "Machine Learning for Asset Managers", Ch. 5 (adapted)
from scipy.stats import linregress

def trend_scan_labels(
    close: pd.Series,
    min_window: int = 3,
    max_window: int = 10,
    t_stat_threshold: float = 1.5,
) -> pd.Series:
    """
    Returns pd.Series with values: +1 (uptrend) or -1 (downtrend).
    Uses max-|t-stat| window. If no window exceeds threshold → 0.
    """
    labels: dict = {}
    arr = close.values
    for i, t in enumerate(close.index):
        best_t = 0.0
        best_label = 0
        for w in range(min_window, max_window + 1):
            end = i + w + 1
            if end > len(arr):
                break
            y = arr[i : end]
            x = np.arange(len(y))
            _, _, _, _, stderr = linregress(x, y)
            slope = (y[-1] - y[0]) / (len(y) - 1)
            # t-stat = slope / stderr (degrees of freedom = n-2)
            result = linregress(x, y)
            t_val = result.slope / result.stderr if result.stderr > 0 else 0.0
            if abs(t_val) > abs(best_t):
                best_t = t_val
                best_label = 1 if t_val > 0 else -1
        labels[t] = best_label if abs(best_t) >= t_stat_threshold else 0
    return pd.Series(labels, dtype=int)
```

### Pattern 3: Meta-Classifier Walk-Forward Loop

**What:** Direct adaptation of `vol_forecast.py`'s `_fit_single_coin()`. Key difference: embargo gap prevents label leakage from the triple-barrier forward horizon.

**Embargo rule:** If train ends at index `start`, test begins at `start + embargo` (not `start`). This prevents the label at train[start] from including price data that overlaps with test features.

**Example:**
```python
# [ASSUMED] — adapted from vol_forecast.py pattern in codebase
def _walkforward_meta_cv(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int = 252,
    step: int = 21,
    embargo: int = 5,
    model_type: str = "logreg",
) -> dict:
    """Expanding window with embargo. Returns per-fold precision/recall/F1."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import precision_score, recall_score, f1_score

    data = pd.concat([X, y.rename("label")], axis=1).dropna()
    n = len(data)

    fold_results = []
    for start in range(min_train, n - step - embargo + 1, step):
        train = data.iloc[:start]
        # Embargo: skip [start..start+embargo], test on [start+embargo..start+embargo+step]
        test_start = start + embargo
        test_end = test_start + step
        if test_end > n:
            break
        test = data.iloc[test_start:test_end]

        X_train = train.drop(columns=["label"]).values
        y_train = train["label"].values
        X_test = test.drop(columns=["label"]).values
        y_test = test["label"].values

        # Require at least both classes in train fold
        if len(set(y_train)) < 2:
            continue

        if model_type == "logreg":
            clf = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        else:
            from lightgbm import LGBMClassifier
            clf = LGBMClassifier(n_estimators=100, max_depth=4,
                                 learning_rate=0.05, n_jobs=1, verbose=-1)

        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        fold_results.append({
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "n_trades_taken": int(y_pred.sum()),
            "n_trades_skipped": int((y_pred == 0).sum()),
        })

    return {"folds": fold_results, "n_folds": len(fold_results)}
```

### Pattern 4: walkforward.py Extension (non-breaking)

**What:** Add `meta_filter: pd.Series | None = None` to `run_walkforward()`. When provided, positions are masked to 0 wherever `meta_filter == 0`. Existing callers pass nothing (default None = no change).

**Example:**
```python
# Extend run_walkforward_with_details signature:
def run_walkforward_with_details(
    prices: pd.DataFrame,
    signals: pd.Series,
    costs: float = 0.001,
    min_train: int = 252,
    step: int = 63,
    meta_filter: pd.Series | None = None,  # NEW — optional, non-breaking
) -> dict[str, Any]:
    ...
    # After computing position from signals.shift(1):
    if meta_filter is not None:
        meta_aligned = meta_filter.reindex(close.index).fillna(0)
        position = position * meta_aligned  # mask to 0 when meta_label=0
    ...
```

### Pattern 5: Feature Construction (shift-safe)

**What:** `build_meta_features(df)` constructs the 10-feature matrix. All features are shifted BEFORE returning the DataFrame, so callers never need to remember to shift.

**Critical detail:** `onchain_health` defaults to 0.5 (neutral) when unavailable — this is locked in CONTEXT.md. This means the feature always has a value and never causes NaN-dropna to silently remove rows.

### Anti-Patterns to Avoid

- **Look-ahead in triple-barrier features:** Do NOT compute `atr_norm` as `ATR[t] / price[t]` without shift. Must be `ATR[t-1] / price[t-1]` — use `shift(1)` on ATR values before adding to feature matrix.
- **Fitting on entire dataset before walk-forward split:** The classifier must only see training folds during fit. Final model refit on all data is fine for `predict_meta_label()` but must not be used to produce OOS metrics.
- **Insufficient OOS folds:** If `n_folds < 10`, emit `finding="negative"` with reason "insufficient_data" — do not report unreliable metrics.
- **No embargo:** Skipping the 5-day embargo gap allows the label at the end of the training window (whose outcome period extends 5 days into the future) to contaminate the test window features. This violates the point-in-time rule.
- **Binary label collapse:** Triple-Barrier produces +1/−1/0. Meta-classifier needs binary (0/1). Map: `label_binary = (label == 1).astype(int)`. Do NOT drop 0 labels — they represent "time barrier" (uncertain trade) and are meaningful "skip" signals.
- **Imbalanced label warnings from LogReg:** Set `class_weight='balanced'` if positive class < 30% of labels. Document this in the model config dict.
- **Using scipy.stats.linregress result fields incorrectly:** `linregress` returns a `LinregressResult` named tuple. Fields are `.slope`, `.intercept`, `.rvalue`, `.pvalue`, `.stderr` (std error of slope). The t-statistic is `slope / stderr`, NOT `rvalue`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Linear regression t-statistic | Manual t-stat formula | `scipy.stats.linregress` | Correct degrees of freedom, already in deps |
| LogisticRegression convergence | Custom gradient descent | `sklearn.linear_model.LogisticRegression` | L2 regularization, numerical stability, solver selection |
| LightGBM binning/boosting | Custom gradient boosting | `lightgbm.LGBMClassifier` | Already in deps, same as vol_forecast pattern |
| Precision/Recall/F1 | Manual TP/FP/FN counting | `sklearn.metrics.precision_score` etc. | Handles zero_division edge case correctly |
| Triple-Barrier barriers | mlfinlab | Hand-roll 30 lines | mlfinlab is NOT in deps; formula is simple |
| Trend-Scan | mlfinlab | Hand-roll with scipy.stats.linregress | Same reason — simpler and no new dep |

**Key insight:** The meta-labeling formulas are straightforward enough to hand-roll correctly in ~100 lines, and adding mlfinlab as a dependency would add a complex transitive dependency that conflicts with the project's lean dependency philosophy.

---

## Common Pitfalls

### Pitfall 1: Look-Ahead at the Label/Feature Boundary

**What goes wrong:** Developer confuses "label uses future prices" with "look-ahead contamination". Triple-Barrier labels legitimately look forward in price (that's their purpose). The violation is if features at time t also use price[t] (same-day price) instead of price[t-1] (shifted).

**Why it happens:** The shift(1) rule for features is easy to forget when also handling forward-looking labels in the same function.

**How to avoid:** `build_meta_features()` must internally call `.shift(1)` on ALL derived columns before returning. The guard in `guards.py` (`assert_no_lookahead`) is the automated check. Add meta feature column names to the guard call in tests.

**Warning signs:** `assert_no_lookahead` raises `LookAheadError` for any feature column. OOS precision suspiciously high (>80%) on any coin.

### Pitfall 2: Label Horizon Overlap with Embargo

**What goes wrong:** The last training label (at train_end=t) has its outcome determined by prices up to t+5. The first test feature window starts at t+1. Without an embargo, test features at t+1 are computed from price data that overlaps with the label outcome period.

**Why it happens:** Embargo is easy to forget when copying the vol_forecast walk-forward loop (vol_forecast has no embargo because HAR targets are shift(−1) with no compounding forward window).

**How to avoid:** Always slice: `test = data.iloc[train_end + embargo : train_end + embargo + step]`.

**Warning signs:** Suspiciously high OOS precision (>70%) on first few folds.

### Pitfall 3: Class Imbalance in Binary Labels

**What goes wrong:** If only 15-20% of Triple-Barrier labels are +1, LogisticRegression defaults to predicting 0 for everything (trivially high accuracy, zero precision). OOS precision = 0.0, n_trades_taken = 0.

**Why it happens:** Crypto tends to trend, so upper barriers are hit less often than expected when asymmetric (2× up, 1× down barriers).

**How to avoid:** Use `class_weight='balanced'` in `LogisticRegression()` by default. Check label distribution before fit; if pos_class < 20%, log a warning.

**Warning signs:** `precision_score(zero_division=0)` returns 0.0 for all folds; `n_trades_taken = 0` across all folds.

### Pitfall 4: Triple-Barrier Label at Series Boundaries

**What goes wrong:** The last `horizon` bars of the price series have incomplete forward windows. Label computation loops off the end of the array.

**Why it happens:** Naive forward-scan loop uses `close.iloc[i+1 : i+horizon+1]` without checking bounds.

**How to avoid:** Use `min(i + horizon + 1, len(close))` as the slice upper bound. The last `horizon` labels will be 0 (time barrier reached with fewer bars) — this is correct and expected. Drop these rows from training via `dropna()` on the full dataset before the walk-forward split.

**Warning signs:** `IndexError` in `triple_barrier_labels()`. Label series shorter than expected.

### Pitfall 5: walkforward.py Backward Compatibility

**What goes wrong:** Adding `meta_filter` parameter to `run_walkforward()` breaks existing callers if parameter is not optional with a default.

**Why it happens:** Forgetting to add `= None` default or to update `run_walkforward()` wrapper (which calls `run_walkforward_with_details()`).

**How to avoid:** Add to BOTH `run_walkforward()` and `run_walkforward_with_details()`. Pass through to the internal call. Existing test suite in `test_walkforward.py` will catch any regression immediately (it calls these functions without the new param).

**Warning signs:** `TypeError: run_walkforward() got an unexpected keyword argument` in any test.

### Pitfall 6: Minimum Folds Check

**What goes wrong:** BTC has plenty of data (>3000 days), but edge cases like a test coin with only 500 days + 252 min_train + 5 embargo + 21 step = only ~11 folds. With embargo gaps reducing effective folds further, the result may have too few folds for reliable precision estimates.

**Why it happens:** Embargo adds dead zones between each fold, reducing effective fold count.

**How to avoid:** After the walk-forward loop, check `n_folds >= 10`. If `n_folds < 10`, return `MetaLabelReport` with `finding="negative"` and `finding_reason="insufficient_oos_folds"`.

---

## Code Examples

### Feature Matrix Construction (verified pattern)

```python
# [ASSUMED] — based on vol_forecast.py shift(1) pattern from codebase
def build_meta_features(
    df: pd.DataFrame,  # must contain close, high, low + sub_scores
) -> pd.DataFrame:
    """
    All outputs are shift(1) so feature@t uses only data <= t-1.
    df must have columns: close, high, low, ma_signal, macd_signal,
    rsi_signal, vol_pred, momentum_rank (optional: onchain_health).
    """
    from backend.application.signals.indicators import rsi as compute_rsi
    from backend.application.signals.indicators import macd as compute_macd
    from backend.application.signals.indicators import atr as compute_atr

    close = df["close"]
    high = df.get("high", close)   # fallback if OHLCV not complete
    low = df.get("low", close)

    # Sub-scores (already binary 0/1, but shift anyway)
    ma_s = df["ma_signal"].shift(1)
    macd_s = df["macd_signal"].shift(1)
    rsi_s = df["rsi_signal"].shift(1)
    consensus_score = (ma_s + macd_s + rsi_s) / 3.0

    # Raw indicators (continuous)
    rsi_val = compute_rsi(close).shift(1)
    _, _, macd_hist = compute_macd(close)
    macd_hist = macd_hist.shift(1)
    atr_vals = compute_atr(high, low, close)
    atr_norm = (atr_vals / close.replace(0, float("nan"))).shift(1)

    # From vol_forecast + factors
    vol_pred_col = df.get("vol_pred", pd.Series(float("nan"), index=df.index)).shift(1)
    mom_rank = df.get("momentum_rank", pd.Series(float("nan"), index=df.index)).shift(1)
    onchain = df.get("onchain_health", pd.Series(0.5, index=df.index)).shift(1)

    return pd.DataFrame({
        "ma_signal": ma_s,
        "macd_signal": macd_s,
        "rsi_signal": rsi_s,
        "consensus_score": consensus_score,
        "rsi_value": rsi_val,
        "macd_hist": macd_hist,
        "atr_norm": atr_norm,
        "vol_pred": vol_pred_col,
        "momentum_rank": mom_rank,
        "onchain_health": onchain.fillna(0.5),
    }, index=df.index)
```

### Binary Label Mapping

```python
# Triple-Barrier returns +1/-1/0. For binary classifier, map to buy=1 / no-trade=0:
# +1 → 1 (upper barrier hit: trade was correct)
# -1 → 0 (lower barrier hit: trade would have lost)
#  0 → 0 (time barrier: no strong move — treat as skip)
label_binary = (triple_barrier_labels_series == 1).astype(int)
```

### Guards.py Extension

```python
# Extend assert_no_lookahead call in tests to include meta features:
meta_feature_cols = [
    "ma_signal", "macd_signal", "rsi_signal", "consensus_score",
    "rsi_value", "macd_hist", "atr_norm", "vol_pred",
    "momentum_rank", "onchain_health",
]
assert_no_lookahead(df_with_close, feature_cols=meta_feature_cols, price_col="close")
```

### MetaLabelReport Schema (from CONTEXT.md — exact)

```python
from typing import Literal
from pydantic import BaseModel

class MetaLabelReport(BaseModel):
    coin: str
    label_method: Literal["triple_barrier", "trend_scan"]
    classifier: Literal["logreg", "lgbm"]
    n_folds: int
    oos_precision: float
    oos_recall: float
    always_trade_sharpe: float
    always_trade_calmar: float
    meta_filtered_sharpe: float
    meta_filtered_calmar: float
    n_trades_always: int
    n_trades_filtered: int
    beats_baseline: bool
    finding: Literal["positive", "secondary_pass", "negative"]
    finding_reason: str
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| mlfinlab for Triple-Barrier | Hand-roll from paper | Per CONTEXT.md decision | No new dependency; formula is simple enough |
| Purged K-Fold CV | Expanding walk-forward only | CONTEXT.md decision | Simpler, matches V4-1 consistency |
| Full mlfinlab Trend-Scan | Hand-roll with scipy.stats.linregress | Per CONTEXT.md decision | 20 lines, same correctness |

**Deprecated/outdated:**
- mlfinlab library: Not in deps, not to be added. The relevant formulas (Triple-Barrier, Trend-Scan) are hand-rollable from the López de Prado papers.
- Purged K-Fold CV: The CONTEXT.md explicitly mandates expanding window only (consistent with V4-1).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Binary label mapping: +1→1, -1→0, 0→0 (treat time-barrier as "skip") | Code Examples | If time-barrier (0) should be excluded rather than mapped to skip, label distribution changes. Impact: moderate — document choice explicitly in code. |
| A2 | `class_weight='balanced'` default for LogisticRegression | Pitfall 3 | If labels are balanced, this slightly hurts precision. Impact: low — can override per fold. |
| A3 | `scipy.stats.linregress` t-stat field is `.stderr` (not SE of residuals) | Pattern 2 | If API differs in scipy 1.13, t-stat calculation is wrong. Impact: high. Mitigation: test on synthetic data with known slope. |
| A4 | Trend-Scan uses `max_|t-stat|` window selection strategy | Pattern 2 | Alternative: use first-window-exceeding-threshold. Impact: low — both are valid implementations. |

---

## Open Questions

1. **Label threshold for binary conversion**
   - What we know: Triple-Barrier returns +1 (upper hit), −1 (lower hit), 0 (time). Labels designed for classification where 1=take trade.
   - What's unclear: Should time-barrier labels (0) be excluded from training rather than treated as "don't take trade"? Exclusion reduces training set; inclusion makes 0 mean two different things.
   - Recommendation: Keep mapping (0→0, time-barrier=skip) for simplicity. Document in code. If precision is consistently poor, revisit exclusion in the negative finding report.

2. **Label alignment to consensus signal dates**
   - What we know: Triple-Barrier labels are computed on raw price series (every bar). Consensus signals fire on a subset of bars.
   - What's unclear: Should labels be computed only for bars where consensus=1 (reducing training set) or on all bars (more training data but features include non-consensus bars)?
   - Recommendation: Compute labels on ALL bars, filter by consensus=1 before fitting (train only on bars where consensus fires). This maximizes interpretability: the classifier learns "given consensus fires, should I take it?"

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scikit-learn | LogisticRegression | ✓ | 1.9.0 | — |
| lightgbm | LGBMClassifier fallback | ✓ | 4.6.0 | — |
| scipy | linregress for Trend-Scan t-stat | ✓ | — (in deps >=1.13) | — |
| numpy | Triple-Barrier array ops | ✓ | 2.2.6 | — |
| pandas | Time series alignment | ✓ | 3.0.3 | — |
| pytest | Test suite | ✓ | In dev deps | — |

**Missing dependencies with no fallback:** None — all required packages are confirmed present.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.1 |
| Config file | `pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `pytest backend/tests/unit/application/test_meta_label.py -q` |
| Full suite command | `pytest backend/tests/unit -q --cov=backend --cov-fail-under=80` |

### Phase Requirements → Test Map

| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| ML-01 | Triple-Barrier labels correct on synthetic data | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_triple_barrier_labels_synthetic -x` | ❌ Wave A |
| ML-02 | Trend-Scan labels correct direction on synthetic uptrend/downtrend | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_trend_scan_labels_direction -x` | ❌ Wave A |
| ML-03 | Look-Ahead-Guard: meta features at t use only data ≤ t-1 | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_meta_features_no_lookahead -x` | ❌ Wave A |
| ML-04 | Label horizon isolation: label@t starts at price[t], not before | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_label_horizon_isolation -x` | ❌ Wave A |
| ML-05 | Classifier walk-forward: OOS precision > 50% on synthetic pattern | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_classifier_oos_above_random -x` | ❌ Wave B |
| ML-06 | No-snooping: classifier never fitted on OOS folds | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_no_snooping -x` | ❌ Wave B |
| ML-07 | Baseline comparison on same OOS dates | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_baseline_same_oos_period -x` | ❌ Wave C |
| ML-08 | walkforward.py meta_filter: backward compatible (no param = no change) | unit | `pytest backend/tests/unit/application/test_walkforward.py::test_meta_filter_backward_compat -x` | ❌ Wave C |
| ML-09 | REST endpoint returns valid MetaLabelReport Pydantic | unit | `pytest backend/tests/unit/application/test_meta_label.py::test_rest_returns_pydantic -x` | ❌ Wave D |
| ML-10 | Coverage gate ≥ 80% | gate | `pytest --cov=backend --cov-fail-under=80` | CI |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/unit/application/test_meta_label.py -q`
- **Per wave merge:** `pytest backend/tests/unit -q --cov=backend --cov-fail-under=80`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/unit/application/test_meta_label.py` — covers ML-01 through ML-09 (all new)
- [ ] `backend/application/signals/meta_label.py` — implementation target

*(test_walkforward.py and test_guards.py already exist — extend, not create)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Read-only endpoint, no auth required (matches existing signals API) |
| V3 Session Management | no | Stateless GET endpoint |
| V4 Access Control | no | No write operations |
| V5 Input Validation | yes | `coin` path param: validate against `_CRYPTO_UNIVERSE` whitelist (same as existing backtest endpoint pattern) |
| V6 Cryptography | no | No cryptographic operations |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path param injection (coin name) | Tampering | Whitelist check against `_CRYPTO_UNIVERSE` list; return 404 if not found (same pattern as `get_backtest()`) |
| Computation DoS (large date range) | DoS | Data fetched via stub prices (n=500) same as existing backtest; no user-controlled window size |

---

## Project Constraints (from CLAUDE.md)

Actionable directives that the planner must verify compliance against:

1. **Test-First (TDD):** Tests must be written BEFORE implementation for domain code, quant models, and application services. `pytestmark = pytest.mark.unit` required in all unit test files.
2. **Pydantic on all public interfaces:** MetaLabelReport must be Pydantic (already in CONTEXT.md).
3. **CI green before merge:** Coverage ≥ 80% is a CI gate (`fail_under = 80` in pyproject.toml).
4. **No LLM in signal computation:** Meta-classifier is sklearn/LightGBM only — no Claude/LLM calls.
5. **Async pattern:** `await asyncio.to_thread(sync_function, arg)` — NOT `run_in_executor`. The REST endpoint wrapper must follow this pattern (see existing `run_walkforward` async wrapper in routers/signals.py).
6. **Branch convention:** Feature branch `feat/v4-2-meta-labeling` from `main`. PR to `main`. No direct pushes.
7. **ruff + mypy:** `ruff check backend/` + `ruff format --check backend/` + `mypy backend/` must all pass. mypy is `strict = true` (but tests have `disallow_untyped_defs = false`).
8. **line-length = 100** (ruff). Keep function docstrings and code within 100 chars.
9. **Conventional Commits:** e.g. `feat(meta-label): add triple_barrier_labels() + tests`.
10. **No mlfinlab dependency:** Not in pyproject.toml, not to be added (hand-roll instead).
11. **No LLM fixtures in CI:** No live API calls in tests. Meta-classifier tests use synthetic price data only.
12. **Floats for returns (not Decimal):** Sharpe/Calmar/Precision are floats — acceptable. Only money amounts use Decimal (not applicable here).

---

## Sources

### Primary (HIGH confidence)

- `backend/application/signals/vol_forecast.py` — walk-forward pattern, LightGBM lazy import, expanding window logic [VERIFIED: codebase]
- `backend/application/backtest/walkforward.py` — extension target, meta_filter integration point [VERIFIED: codebase]
- `backend/application/backtest/guards.py` — assert_no_lookahead extension point [VERIFIED: codebase]
- `backend/application/signals/indicators.py` — atr(), rsi(), macd() reuse for feature construction [VERIFIED: codebase]
- `pyproject.toml` — scikit-learn>=1.4, lightgbm>=4.3, scipy>=1.13 confirmed in deps [VERIFIED: codebase]
- `python3 -c "import sklearn; ..."` — sklearn 1.9.0, lightgbm 4.6.0 confirmed installed [VERIFIED: runtime]

### Secondary (MEDIUM confidence)

- López de Prado, "Advances in Financial Machine Learning" Ch. 3 (Triple-Barrier) — formula cited in CONTEXT.md [CITED: CONTEXT.md canonical_refs]
- López de Prado, "Machine Learning for Asset Managers" Ch. 5 (Trend-Scan) — formula adapted [CITED: CONTEXT.md canonical_refs]
- `sklearn.linear_model.LogisticRegression` API — L2 default, max_iter, class_weight [ASSUMED: training knowledge; version 1.9.0 confirmed installed]
- `scipy.stats.linregress` return fields (.slope, .stderr) [ASSUMED: training knowledge; scipy confirmed in deps]

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages confirmed in pyproject.toml and runtime
- Architecture: HIGH — direct extension of verified V4-1 codebase patterns
- Triple-Barrier formula: HIGH — cited in CONTEXT.md from López de Prado source
- Trend-Scan formula: MEDIUM — adapted from paper; scipy.stats.linregress API assumed correct
- Pitfalls: HIGH — derived from actual codebase analysis (vol_forecast.py, guards.py patterns)

**Research date:** 2026-06-21
**Valid until:** 2026-07-21 (stable deps; re-verify if scikit-learn API changes)
