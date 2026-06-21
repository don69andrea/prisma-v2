# Phase 1 Context — V4-1 Signal-Engine

**Phase:** 1  
**Name:** V4-1 Signal-Engine  
**Date:** 2026-06-21  
**Source:** docs/PRISMA_V4-1_PHASENPLAN_Signal-Engine.md (Teil A + Teil B) — spec imported directly, no gray-area discussion needed

<domain>
Deterministic Signal Engine for Top-10 crypto universe. Delivers `SignalVector` (Pydantic) per coin from 3 layers: (1) factor ranking WAS, (2) indicator consensus WANN, (3) vol-forecast sizing WIEVIEL. Backed by strict walk-forward backtests that reproduce the PoC finding. NO agents, NO UI this phase.
</domain>

<spec_lock>
Requirements locked from: `docs/PRISMA_V4-1_PHASENPLAN_Signal-Engine.md` (Teil A)
MUST read before planning: that file is the authoritative spec.
</spec_lock>

<decisions>

## Data Model (migrations 0037-0039)

- **`crypto_universe`** (new): coin_id PK, symbol (BTC-USD), name, active bool, added_at. Seed: BTC/ETH/SOL/BNB/XRP/ADA/AVAX/DOGE/LINK/DOT.
- **`crypto_onchain_history`** (new): (coin_id, date) PK, mvrv_z, realized_cap, active_addresses, tx_volume, exchange_netflow, source. Source: Coin Metrics Community.
- **`market_sentiment`** (new): date PK, fear_greed int, fg_classification str, source. Source: alternative.me.
- **`vol_forecast`** (new): (coin_id, date, horizon) PK, pred_vol, realized_vol (nullable), model_version.
- **`signal_outcomes`** (extend/new): coin_id, date, action, size_factor, sub_scores JSONB, realized_fwd_return nullable.
- **Point-in-time rule:** ALL tables carry observation date. No feature at time t may use data > t. Enforced by Look-Ahead-Guard tests.

## Signal Engine Modules — `backend/application/signals/`

- **`indicators.py`**: `sma`, `ema`, `macd`, `rsi`, `bollinger`, `atr` — vectorized, tested vs `ta`-lib reference (Δ < 1e-6).
- **`consensus.py`**: `consensus_vote(df, cfg) -> Series[0/1]` — 2-of-3 default (MA+MACD+RSI). Configurable weights.
- **`vol_forecast.py`**: HAR-Baseline → LightGBM. `fit_walkforward()`, `predict_vol(coin, date)`. Walk-Forward mandatory. LightGBM only if OOS > HAR.
- **`sizing.py`**: `vol_target_size(pred_vol, target=0.60, cap=1.5)`, `drawdown_brake()`. Returns size_factor ∈ [0, cap].
- **`factors.py`**: `cross_sectional_momentum()`, `onchain_health_score()`. Layer 1 ranking.
- **`meta_label.py`**: OPTIONAL (Wave 6). `triple_barrier_labels()`, `fit_meta_classifier()`. Blocks nothing if absent.
- **`signal_service.py`**: `evaluate(coin, asof) -> SignalVector`. Orchestrates Layers 1-3.

## Backtest Engine — `backend/application/backtest/`

- **`walkforward.py`**: Expanding-Window (embargo = horizon). Exposure-Matched Baseline mandatory. Net costs 0.1%. Outputs: equity, Sharpe/Calmar/MaxDD, per-fold table, trade list, CI/N.
- **`guards.py`**: Look-Ahead-Guard: assert Feature@t uses only data ≤ t-1. Automated shift-check.

## API — `backend/interfaces/rest/routers/signals.py`

Three read-only endpoints (no writes):
- `GET /api/v1/signals` → `list[SignalVector]`
- `GET /api/v1/signals/{coin}` → `SignalVector`
- `GET /api/v1/backtest/{coin}` → `BacktestReport`

## Pydantic Schemas

```python
class SignalVector(BaseModel):
    coin: str
    asof: date
    action: Literal["BUY", "HOLD", "SELL"]   # SELL = cash, never short
    size_factor: float = Field(ge=0.0, le=1.5)
    consensus: str                             # e.g. "3/3"
    sub_scores: dict[str, float]              # ma, macd, rsi, bb, vol_pred, momentum_rank, onchain
    confidence: float = Field(ge=0.0, le=1.0)
    disclaimer: str = "Entscheidungsunterstützung, kein Anlagerat."

class BacktestReport(BaseModel):
    coin: str; cagr: float; sharpe: float; max_dd: float; calmar: float
    beats_exposure_matched: bool
    n_trades: int; equity_curve: list[tuple[date, float]]
```

## Test Strategy (Test-First, all A7 cases)

1. Indicator correctness vs `ta`-lib reference on sample data, Δ < 1e-6
2. Look-ahead guard: automated shift-check (Signal@t never uses data@t)
3. Consensus logic: 2-of-3 truth table
4. Vol-forecast walk-forward: OOS-R² > 0 vs constant baseline on ≥2 coins
5. Sizing monotonicity: higher pred_vol → smaller size_factor; bounds [0, cap]
6. Backtest baselines: exposure-matched + buy&hold computed; `beats_exposure_matched` correct
7. Net costs: turnover × 0.1% subtracted (strategy return < gross on trade days)
8. No-shorting: `action=="SELL"` ⇒ target exposure = 0, never negative
9. API schema: all endpoints return valid Pydantic (no freetext)
10. Coverage gate: ≥ 80%

## Success Criterion (A1)

Signal Engine beats exposure-matched baseline on Sharpe **AND** Calmar in walk-forward, net costs, over the Top-10 universe. This reproduces the PoC finding (BTC Calmar 1.38 vs 0.60).

## Build Order — Waves (from Teil B)

- **Wave 0** (Setup): Branch `feat/v4-1-signal-engine`, `pip install lightgbm ta`
- **Wave 1** (Data, parallel 1a‖1b‖1c): Universe+OHLCV seed, On-Chain adapter, Fear&Greed adapter
- **Wave 2** (Signal Engine core, 2a→2b, 2c parallel): Indicators+consensus, Factors, Vol-Forecast
- **Wave 3** (Sizing + Service): Sizing, signal_service.py → SignalVector
- **Wave 4** (Backtest): walkforward.py + guards.py, Look-Ahead-Guard, Per-Fold-Report
- **Wave 5** (API): 3 read-only endpoints
- **Wave 6** (optional Meta-Label): only if Waves 1-5 done with time remaining
- **Wave 7** (Gate + PR): pytest --cov ≥ 80%, AI-USAGE.md entry, PR against develop

</decisions>

<canonical_refs>
- `docs/PRISMA_V4-1_PHASENPLAN_Signal-Engine.md` — PRIMARY SPEC (Teil A = spec, Teil B = wave contracts). MUST READ.
- `docs/PRISMA_V4_PROJEKTPLAN.md` — V4 overall plan, architecture diagram
- `docs/PRISMA_V4_AGENTS.md` — Agent brief (V4-3 phase, NOT this phase — for context only)
- `docs/AGENTS.md` — Repo rules: Spec-First, Test-First, Pydantic, CI-green, Coverage ≥80%
- `CLAUDE.md` — Claude Code conventions
- `docs/research/poc_feasibility.py` — PoC backtest script (reference implementation)
- `docs/research/indicator_backtest.py` — Indicator backtest (reference for Vol+consensus logic)
- `docs/research/poc_results.txt` — PoC results to reproduce
- `docs/research/indicator_results.txt` — Indicator results to reproduce
- `backend/application/agents/steuer_agent.py` — Gold standard agent pattern (NOT for this phase, but code style ref)
- `backend/infrastructure/adapters/yfinance_swiss.py` (if exists) — Extension point for crypto price adapter
- `backend/alembic/versions/` — Latest migration: 0022; next: 0037
- `pyproject.toml` — Python deps, ruff/mypy config, coverage settings
</canonical_refs>

<code_context>
**Reusable from existing code:**
- `backend/alembic/env.py` — migration setup pattern (copy for 0037-0039)
- `backend/infrastructure/adapters/` — adapter pattern; yfinance_swiss.py as crypto price adapter starting point
- `backend/application/services/backtest_service.py` — existing backtest (for SMI); must NOT break, but V4-1 builds a NEW engine in `backend/application/backtest/`
- `backend/interfaces/rest/routers/` — router pattern (copy for signals.py)
- `backend/interfaces/rest/schemas/backtest.py` — existing Pydantic schema pattern
- `backend/tests/unit/` — test structure to follow
- `backend/tests/integration/` — integration test pattern with aiosqlite

**Do NOT touch:**
- `backend/application/services/signal_aggregation_service.py` — SMI signals, must stay untouched
- `backend/application/services/signal_validation_service.py` — SMI validation, must stay untouched
- `backend/application/agents/` — all existing agents untouched this phase
- `frontend/` — no UI changes this phase
</code_context>
