# Phase 2 Context — V4-2 Meta-Labeling

**Phase:** 2  
**Name:** V4-2 Meta-Labeling  
**Date:** 2026-06-21  
**Source:** Session prompt (Andrea Petretta) — all decisions locked from user brief + codebase scout

<domain>
Binary meta-classifier "take trade now / skip" (López de Prado Meta-Labeling) that filters the
V4-1 consensus signal. Input: V4-1 indicator features. Output: 0/1 label "trade YES / NO".
Strict walk-forward only. Honest comparison against always-trade baseline. Negative finding is valid.
NO agents, NO UI this phase.
</domain>

<decisions>

## Labeling Method

- **Implement BOTH** Triple-Barrier (López de Prado) AND Trend-Scanning labels.
- Compare both on BTC + ETH in walk-forward; choose the one with higher precision on the test folds.
- **Triple-Barrier parameters** (starting point, tunable in research):
  - Upper barrier: +2× ATR(20)
  - Lower barrier: −1× ATR(20) (asymmetric — trend-following biased)
  - Time barrier: 5 trading days (same as V4-1 forward return horizon)
- **Trend-Scanning**: Scan forward 3–10 bars; label = direction of first statistically significant move
  (t-statistic on linear fit > 1.5).
- Labels are computed on the **raw price series**, then aligned to consensus signal dates.
- **Point-in-time rule**: Label at time t uses price data ONLY from [t, t+horizon]. Features at t use
  data ≤ t−1. Look-Ahead-Guard must catch any violation.
- If both label methods produce near-identical results (Δprecision < 5%), use Triple-Barrier
  (more interpretable for the professor, standard in literature).

## Classifier Algorithm

- **Primary: LogisticRegression** (sklearn, L2 regularization, max_iter=1000).
  Reason: coefficients = direct feature importances → satisfies Renold's explainability requirement.
- **Fallback: LightGBM** — add only if LogReg OOS precision < LightGBM OOS precision by >5pp
  AND LogReg precision < 55% (i.e., essentially random). Use same LightGBM setup as vol_forecast.py.
- Do NOT use RandomForest — slower, no advantage over LightGBM if LightGBM is already in deps.
- Both models wrapped in the same `fit_meta_classifier(X, y, model='logreg'|'lgbm')` interface.

## Feature Set (input to classifier)

All features from `SignalVector.sub_scores` dict + raw indicator values computed by indicators.py:

| Feature | Source | Rationale |
|---------|--------|-----------|
| `ma_signal` | consensus.py output | binary MA crossover direction |
| `macd_signal` | consensus.py output | binary MACD signal |
| `rsi_signal` | consensus.py output | binary RSI direction |
| `consensus_score` | sum/3 of above | strength of consensus |
| `rsi_value` | indicators.py raw | continuous RSI (0–100); overbought/oversold context |
| `macd_hist` | indicators.py raw | MACD histogram magnitude |
| `atr_norm` | ATR/price | normalized volatility regime |
| `vol_pred` | vol_forecast.py | predicted annualized vol |
| `momentum_rank` | factors.py | cross-sectional momentum rank (0–1) |
| `onchain_health` | factors.py | if available, else 0.5 (neutral fill) |

Feature construction in `meta_label.py` → `build_meta_features(df) -> pd.DataFrame`.
All features shift(1) enforced before passing to classifier (Look-Ahead-Guard).

## Walk-Forward Structure

- **Expanding window** (same pattern as vol_forecast.py / walkforward.py):
  - `min_train = 252` trading days
  - `step = 21` days (ca. 1 month → more OOS folds, stable estimate)
  - `embargo = 5` days (gap between train end and test start — prevents label-leakage from
    triple-barrier horizon)
- **Minimum OOS folds required for valid result**: ≥ 10 folds (i.e., dataset needs ≥ 462 days).
  BTC has ~9.5y = ~3470 days → more than sufficient.
- Walk-forward produces per-fold: precision, recall, F1, n_trades_taken, n_trades_skipped.

## Baseline Comparison

- **"Always-trade" baseline**: Run V4-1 consensus signal WITHOUT meta-filter (every consensus=1 → take trade).
  This is the same engine from V4-1, output already available via `run_walkforward()`.
- **"Meta-filtered" strategy**: Take trade only when consensus=1 AND meta_label=1.
- Comparison must be done on the **same OOS period** (no IS cherry-picking).
- Report both in `MetaLabelReport` Pydantic schema.

## Success Criterion

**Primary (pass):** Meta-filtered strategy beats always-trade baseline on BOTH Sharpe AND Calmar
in OOS walk-forward, net of costs, on BTC and/or ETH.

**Secondary (acceptable pass):** Trade count or max drawdown reduced by ≥10% WITHOUT
Sharpe/Calmar degradation > 5% vs always-trade. (Filter reduces risk without hurting performance.)

**Negative finding (valid result):** If neither holds on any coin → honest negative finding.
Document WHY (e.g., "insufficient signal selectivity", "too few filtered trades for stable estimate").
Do NOT tune parameters until it looks good. Champion/Challenger mentality.

## Pydantic Schemas (new)

```python
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

## Test Strategy (Test-First, before implementation)

1. **Label correctness**: Triple-Barrier on synthetic price series with known barriers → correct 0/1/−1 labels.
2. **Trend-Scan correctness**: Synthetic uptrend/downtrend → expected direction labels.
3. **Look-Ahead-Guard**: meta_features@t must use only data ≤ t−1 (automated shift-check, same as guards.py).
4. **Label horizon isolation**: Label@t uses price data starting AT t (not before). Feature shift ensures no contamination.
5. **Classifier walk-forward**: On synthetic data with known pattern → OOS precision > 50%.
6. **No-snooping**: Classifier fitted only on train folds; OOS folds never seen during fit.
7. **Baseline comparison**: Both "always-trade" and "meta-filtered" computed on same dates.
8. **Coverage gate**: ≥ 80% (CI non-negotiable).
9. **REST endpoint** (if added): returns `MetaLabelReport` Pydantic, no freetext.

## Module Structure

```
backend/application/signals/
    meta_label.py          ← NEW: labels + classifier + feature builder

backend/application/backtest/
    walkforward.py         ← EXTEND: add meta_filter parameter (optional flag, non-breaking)

backend/tests/unit/application/
    test_meta_label.py     ← NEW: all test cases above
    test_walkforward.py    ← EXTEND: add meta_filter integration tests

backend/interfaces/rest/routers/
    signals.py             ← EXTEND: add GET /api/v1/signals/meta-label/{coin}
backend/interfaces/rest/schemas/
    signals.py             ← EXTEND: add MetaLabelReport schema
```

## What NOT to change

- `backend/application/signals/consensus.py` — no changes
- `backend/application/signals/vol_forecast.py` — no changes (output used as feature)
- All SMI services and agents — untouched
- `frontend/` — no UI this phase

## Build Order — Waves

- **Wave A** (Labels): `triple_barrier_labels()`, `trend_scan_labels()`, `build_meta_features()` + tests
- **Wave B** (Classifier): `fit_meta_classifier()`, `predict_meta_label()` walk-forward + tests
- **Wave C** (Backtest integration): extend `walkforward.py` with `meta_filter` flag; `MetaLabelReport`
- **Wave D** (API + coverage gate): `GET /api/v1/signals/meta-label/{coin}`, coverage ≥ 80%, PR

</decisions>

<canonical_refs>
- `backend/application/signals/consensus.py` — V4-1 consensus vote (features source)
- `backend/application/signals/indicators.py` — raw indicator values (features source)
- `backend/application/signals/vol_forecast.py` — vol_pred feature + LightGBM pattern to copy
- `backend/application/signals/factors.py` — momentum_rank, onchain_health features
- `backend/application/backtest/walkforward.py` — expanding walk-forward pattern to extend
- `backend/application/backtest/guards.py` — Look-Ahead-Guard to extend for meta features
- `backend/interfaces/rest/routers/signals.py` — router pattern to extend
- `backend/interfaces/rest/schemas/signals.py` — Pydantic schema pattern to extend
- `backend/tests/unit/application/test_vol_forecast.py` — walk-forward test pattern (copy style)
- `docs/PRISMA_V4_PROJEKTPLAN.md` — §2 Meta-Labeling spec + success criterion
- `docs/PRISMA_V4_AGENTS.md` — §0 iron rule: no LLM computes numbers (context for future phases)
- `docs/AGENTS.md` — Repo rules: Spec-First, Test-First, Pydantic, CI-green, Coverage ≥80%
- `CLAUDE.md` — Claude Code conventions
- `pyproject.toml` — Python deps, ruff/mypy config, coverage settings
</canonical_refs>

<code_context>
**Directly reusable from V4-1:**
- `vol_forecast.py` → `_walk_forward_cv()` pattern: copy expanding-window logic for meta-classifier
- `guards.py` → `assert_no_lookahead()`: extend to also check meta features
- `walkforward.py` → add optional `meta_filter: pd.Series | None = None` param (positions masked to 0 when meta_label=0)
- `indicators.py` → `atr()`, `rsi()`, `macd()` already vectorized — reuse as feature builder
- `test_vol_forecast.py` → copy walk-forward test structure for `test_meta_label.py`

**New dependencies (already in pyproject.toml):**
- `scikit-learn` (LogisticRegression, train_test_split) — check if already in deps
- `lightgbm` — already in deps from vol_forecast.py

**Do NOT touch:**
- Any SMI service or agent
- `consensus.py`, `vol_forecast.py`, `sizing.py`, `factors.py` (read-only inputs to meta_label.py)
- `frontend/`
</code_context>
