---
phase: 1
plan: 07
subsystem: backend/interfaces/rest
tags: [signals, backtest, rest-api, tdd, coverage]
dependency_graph:
  requires: [01-05-PLAN, 01-06-PLAN]
  provides: [GET /api/v1/signals, GET /api/v1/signals/{coin}, GET /api/v1/backtest/{coin}]
  affects: [backend/interfaces/rest/app.py, backend/interfaces/rest/routers/signals.py]
tech_stack:
  added: []
  patterns: [APIRouter, response_model, Depends, in-memory cache, asyncio.to_thread, TDD RED/GREEN]
key_files:
  created:
    - backend/interfaces/rest/routers/signals.py
    - backend/tests/unit/application/test_signal_engine.py
    - backend/tests/integration/test_signals_endpoint.py
  modified:
    - backend/interfaces/rest/app.py
    - backend/application/signals/signal_service.py
    - docs/AI-USAGE.md
decisions:
  - "Zwei separate APIRouter (signals + backtest) statt einer gemeinsamen Route — sauberere Tags und Prefix-Trennung"
  - "In-Memory Cache (TTL 1h) statt Redis — kein neuer Infrastruktur-Aufwand für PoC"
  - "run_walkforward als asyncio.to_thread() gewrapped — CLAUDE.md-Konvention eingehalten"
  - "Stub-Preisdaten (deterministischer Random-Walk) statt Live-DB für Endpoint-Logik"
metrics:
  duration: "~45 Minuten"
  completed: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
---

# Phase 1 Plan 07: Signals REST Endpoints Summary

**One-liner:** Drei read-only REST-Endpoints (signals list, signals detail, backtest) mit Pydantic-Validierung, 1h In-Memory Cache und 93.4% Coverage auf signals/ + backtest/-Modulen.

## Was wurde gebaut

### T01: Signals Router — 3 GET-Endpoints (A7.9)

`backend/interfaces/rest/routers/signals.py` implementiert:

- `GET /api/v1/signals` → `list[SignalVector]`: Iteriert `_CRYPTO_UNIVERSE` (10 Coins), ruft `signal_service.evaluate()` pro Coin auf, 1h In-Memory Cache.
- `GET /api/v1/signals/{coin}` → `SignalVector`: 404 wenn Coin nicht in `_CRYPTO_UNIVERSE`. Nutzt Cache.
- `GET /api/v1/backtest/{coin}` → `BacktestReport`: Eigener `backtest_router` mit Prefix `/api/v1/backtest`. 404 für unbekannte Coins. Async-Wrapper um synchronen `run_walkforward` via `asyncio.to_thread`.

`backend/interfaces/rest/app.py` erweitert um:
```python
app.include_router(signals.router, dependencies=_auth)
app.include_router(signals.backtest_router, dependencies=_auth)
```

### T02: Integrationstests + Coverage Gate (A7.9, A7.10)

`backend/tests/integration/test_signals_endpoint.py` — 6 Tests:
- `test_signals_list_returns_list` — 200, list mit Feldern
- `test_signals_detail_returns_signalvector` — action ∈ {BUY, HOLD, SELL}, size_factor ∈ [0, 1.5]
- `test_signals_unknown_coin_404` — FAKE-USD → 404
- `test_backtest_returns_report` — beats_exposure_matched ist bool
- `test_signalvector_schema_complete` — alle 8 Pflichtfelder vorhanden (A7.9)
- `test_backtest_unknown_coin_404` — FAKE-USD → 404

`backend/tests/unit/application/test_signal_engine.py` — 71 Tests für:
- indicators: sma, ema, rsi, macd, bollinger, atr
- consensus: 2-of-3 vote (6 Szenarien)
- sizing: vol_target_size, drawdown_brake, apply_sizing
- guards: LookAheadError, assert_no_lookahead
- walkforward: run_walkforward (Kernpfad + Metriken)
- vol_forecast: realized_vol, build_har_features, fit_walkforward, predict_vol
- factors: cross_sectional_momentum, onchain_health_score
- signal_service: evaluate (9 Szenarien inkl. onchain + vol_model_info)

## Coverage-Ergebnis (A7.10)

```
Name                                            Stmts   Miss  Cover
-------------------------------------------------------------------
backend/application/backtest/guards.py             21      0  100.0%
backend/application/backtest/walkforward.py        67      5   92.5%
backend/application/signals/consensus.py           13      0  100.0%
backend/application/signals/factors.py             43      1   97.7%
backend/application/signals/indicators.py          38      0  100.0%
backend/application/signals/signal_service.py      72      5   93.1%
backend/application/signals/sizing.py              15      0  100.0%
backend/application/signals/vol_forecast.py       112     14   87.5%
-------------------------------------------------------------------
TOTAL                                             381     25   93.4%
```

**Gate 80% — BESTANDEN: 93.4%**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Timezone-Mismatch in signal_service.evaluate**
- **Found during:** T02 (Unit-Tests)
- **Issue:** `pd.Timestamp(asof)` ohne Timezone-Argument schlägt bei UTC-aware DatetimeIndex fehl (`TypeError: Invalid comparison between dtype=datetime64[us, UTC] and Timestamp`)
- **Fix:** Timezone-Conditional in `signal_service.py:86-90` — `pd.Timestamp(asof, tz="UTC")` wenn Index tz-aware, sonst tz-naive
- **Files modified:** `backend/application/signals/signal_service.py`
- **Commit:** `348a1f3`

**2. [Rule 2 - Missing Critical Functionality] run_walkforward async-Wrapper**
- **Found during:** T01 (Implementierung)
- **Issue:** `run_walkforward` ist synchron mit anderer Signatur als erwartet (`prices: pd.DataFrame` mit `close`-Spalte + `signals: pd.Series`). Kein direkter async-Aufruf möglich.
- **Fix:** Eigene `run_walkforward(coin, prices_df)` async-Wrapper-Funktion im Router — Synthetisiert SMA-Signal, ruft `asyncio.to_thread()` auf (CLAUDE.md-Konvention)
- **Files modified:** `backend/interfaces/rest/routers/signals.py`
- **Commit:** `348a1f3`

### Scope-Abgrenzung

**Stub-Preisdaten (bewusste Entscheidung):** In Produktion müssen echte Preisdaten aus der DB oder einem Market-Data-Provider geladen werden. Die `_make_stub_prices()` Funktion ist als PoC/Fallback markiert. Tracked als bekannter Stub.

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| `backend/interfaces/rest/routers/signals.py:76-86` | `_make_stub_prices()` — deterministischer Random-Walk | Echte Preise kommen aus DB/Market-Data-Provider (nicht Teil dieses Plans) |

## TDD Gate Compliance

- RED-Gate: Commit `b1ccd86` — `test(01-07): failing integration tests signals endpoints RED (A7.9)` ✓
- GREEN-Gate: Commit `348a1f3` — `feat(01-07): signals + backtest REST endpoints GREEN (A7.9) + coverage 93% (A7.10)` ✓
- REFACTOR: Nicht notwendig (Code sauber nach GREEN-Phase)

## Self-Check: PASSED

- `backend/interfaces/rest/routers/signals.py` — FOUND
- `backend/interfaces/rest/app.py` (signals.router + backtest_router registriert) — FOUND
- `backend/tests/integration/test_signals_endpoint.py` — FOUND
- `backend/tests/unit/application/test_signal_engine.py` — FOUND
- Commits b1ccd86, 348a1f3, b087925 — FOUND
- Coverage 93.4% >= 80% — PASSED
