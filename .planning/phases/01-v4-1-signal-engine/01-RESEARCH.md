# Phase 1 Research — V4-1 Signal-Engine

**Date:** 2026-06-21  
**Phase:** 1 — V4-1 Signal-Engine

---

## Existing Patterns to Reuse

### Alembic Migration Pattern
- File: `backend/alembic/versions/0021_add_ml_feature_columns.py`
- Convention: `revision`, `down_revision`, `branch_labels = None`, `depends_on = None`
- Use `op.create_table(...)` for new tables, `op.add_column(...)` for extensions
- Revises chain: 0022 → 0037 → 0038 → 0039 → 0040
- Seed data: use `op.bulk_insert()` inside `upgrade()` for crypto_universe rows

### Adapter Pattern
- Base: `backend/infrastructure/adapters/yfinance_swiss.py`
- All sync I/O via `await asyncio.to_thread(sync_fn, arg)` — NOT `run_in_executor`
- Retry: `_RETRIES = 2`, `_BASE_DELAY = 1.0`, exponential backoff `base * 2**attempt`
- Error: domain-specific error classes, logged with `_logger = logging.getLogger(__name__)`
- No business logic in adapter — returns raw data types (DataFrame, dict)

### FastAPI Router Pattern
- File: `backend/interfaces/rest/routers/` (e.g. `backtests.py`, `decisions.py`)
- `APIRouter(prefix="/api/v1/signals", tags=["signals"])`
- Dependencies: `db: AsyncSession = Depends(get_async_session)`
- Responses: Pydantic models only, `response_model=SignalVector`
- Register in `backend/interfaces/rest/app.py` via `app.include_router(...)`

### Pydantic Schema Pattern
- File: `backend/interfaces/rest/schemas/backtest.py`
- `from pydantic import BaseModel, Field`
- Field validators: `Field(ge=0.0, le=1.5)` for bounded floats
- Literal types: `Literal["BUY", "HOLD", "SELL"]`

### pytest-asyncio Test Pattern
- `pytestmark = pytest.mark.unit` in unit test files
- `@pytest.mark.asyncio` for async tests
- aiosqlite for integration (no live DB in unit tests)
- Fixture in `conftest.py`: `async_session`, `test_client`

---

## Critical Constraints [VERIFIED from codebase]

- **Dependencies to install:** `pip install lightgbm ta --break-system-packages` (not in pyproject.toml yet; add to `[project.dependencies]` AND install in Wave 0 before other waves start)
- **Look-Ahead-Guard:** Signal@t MUST use only data ≤ t-1. Enforce via `df.shift(1)` on all feature columns. Automated test must fail if any feature reads t instead of t-1.
- **SELL = exposure 0:** `action == "SELL"` ⇒ `size_factor = 0.0`. Never negative. Enforced in test A7.8.
- **Coverage ≥ 80%:** `fail_under=80` in pyproject.toml — CI gate. New `signals/` and `backtest/` modules need ≥80% coverage.
- **Do NOT touch:** `signal_aggregation_service.py`, `signal_validation_service.py`, any existing agent files, any frontend files.
- **LightGBM only if OOS > HAR:** Vol-forecast starts with HAR baseline; LightGBM added only if walk-forward OOS-R² is strictly better than HAR-only OOS-R².
- **asyncio.to_thread:** All yfinance and external HTTP calls via `asyncio.to_thread()` (NOT `run_in_executor`).

---

## Data Sources [VERIFIED from CONTEXT.md + PoC scripts]

### yfinance Crypto [VERIFIED from PoC]
```
yfinance.download("BTC-USD", start="2017-01-01", interval="1d")
```
Returns DataFrame with columns: Open, High, Low, Close, Volume, Adj Close.
Ticker format: `{SYMBOL}-USD` (e.g. "BTC-USD", "ETH-USD", "SOL-USD").
Works identically to Swiss equity adapter — same API, different ticker format.
Rate-limit: ~2000 req/day per IP without auth. Backfill once, store in DB.

### Coin Metrics Community API [ASSUMED — not verified in this session]
```
https://community-api.coinmetrics.io/v4/timeseries/asset-metrics
  ?assets=btc,eth
  &metrics=RealizedCap,SplyMVRVCur,AdrActCnt,FlowOutExNtv,FlowInExNtv
  &frequency=1d
  &pretty=true
```
No auth required for community tier. BTC/ETH well-covered; smaller coins may have sparse data.
Field mapping: `SplyMVRVCur` → mvrv_z, `RealizedCap` → realized_cap, `AdrActCnt` → active_addresses.
Exchange netflow = `FlowOutExNtv - FlowInExNtv`.
Fallback: if coin not available in Coin Metrics, set onchain fields to NULL (nullable columns).

### alternative.me Fear & Greed [ASSUMED]
```
https://api.alternative.me/fng/?limit=0&format=json
```
Returns full historical daily index from 2018-02-01. Fields: `value` (int 0-100), `value_classification` (str).
No auth required. Date format: Unix timestamp in `timestamp` field.

---

## Vol-Forecast Technical Approach [VERIFIED from PoC scripts]

### HAR Model (Heterogeneous AutoRegressive)
```
pred_vol_t = a + b1*realized_vol_1d + b2*mean(realized_vol_5d) + c*mean(realized_vol_22d)
```
Realized vol = rolling std of log-returns (annualized: × sqrt(252)).
Features (HAR): `rv_1d`, `rv_5d_avg`, `rv_22d_avg`.
Fit with `sklearn.linear_model.LinearRegression` (OLS baseline, interpretable).

### LightGBM Extension
Additional features: `rv_1d`, `rv_5d_avg`, `rv_22d_avg`, `vol_of_vol_5d` (std of rv_1d over 5d), `vol_ratio_1d_22d` (rv_1d / rv_22d_avg).
Only trained if LightGBM OOS-R² > HAR OOS-R² on the same walk-forward folds.
`LGBMRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, n_jobs=1)`.

### Walk-Forward Protocol
Expanding window: min_train=252 bars, step=63 bars (quarterly refit).
OOS-R² = 1 - SS_res / SS_tot (vs constant-mean baseline).
PoC target: BTC OOS-R² ≥ +52%, ETH ≥ +31%.

---

## Indicator Reference Values [VERIFIED from PoC + ta library]

Use `ta` library for cross-validation:
- `ta.momentum.RSIIndicator(close, window=14).rsi()`
- `ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)`
- `ta.volatility.BollingerBands(close, window=20, window_dev=2)`
- `ta.trend.SMAIndicator(close, window=N).sma_indicator()`

Tolerance for own implementation: Δ < 1e-6 on sample data (allow for floating-point rounding).

---

## Backtest Engine Design [VERIFIED from PoC — poc_feasibility.py]

### Exposure-Matched Baseline
Purpose: isolate timing skill from mere underinvestment.
Construction: compute average exposure fraction of strategy (fraction of days invested).
Apply that fraction continuously as a buy-and-hold fraction (e.g. 55% invested always).
This baseline has the same average cash drag as the strategy but no timing.

### Performance Metrics
- **Sharpe** = (mean_daily_return / std_daily_return) × sqrt(252)
- **MaxDD** = max drawdown from peak
- **Calmar** = CAGR / abs(MaxDD)
- **CAGR** = (final_equity / initial_equity)^(252/n_days) - 1
- **beats_exposure_matched** = strategy.sharpe > baseline.sharpe AND strategy.calmar > baseline.calmar

---

## Project Constraints from CLAUDE.md

- `asyncio.to_thread()` — not `run_in_executor`
- No `tenacity` — manual retry with `_RETRIES = 2`, `_BASE_DELAY = 1.0`
- Pydantic on all outputs — no freetext to REST layer
- TDD-Pflicht: tests before implementation for domain/application code
- `pytestmark = pytest.mark.unit` in unit tests
- `float` for prices/vols (not `Decimal` — Decimal reserved for monetary amounts)
- Ruff line-length=100, mypy strict

---

## RESEARCH COMPLETE
