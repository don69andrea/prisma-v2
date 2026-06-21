---
phase: 1
plan: 05
subsystem: signal-engine
tags: [sizing, vol-targeting, signal-service, pydantic, tdd]
dependency_graph:
  requires: [01-03-PLAN.md, 01-04-PLAN.md]
  provides: [sizing.py, signal_service.py, schemas/signals.py]
  affects: [backend/interfaces/rest/routers/signals.py (Wave 5)]
tech_stack:
  added: []
  patterns: [vol-targeting-sizing, drawdown-brake, 2-of-3-consensus, look-ahead-guard, data-injection-testing]
key_files:
  created:
    - backend/application/signals/sizing.py
    - backend/application/signals/signal_service.py
    - backend/interfaces/rest/schemas/signals.py
    - backend/tests/unit/application/test_sizing.py
    - backend/tests/unit/application/test_signal_service.py
  modified:
    - backend/application/signals/vol_forecast.py (mypy type fixes)
decisions:
  - "apply_sizing(SELL) → 0.0 immer — kein Short, kein negatives Exposure"
  - "evaluate() erhält alle Daten als Parameter — kein I/O drinnen (Testbarkeit)"
  - "Look-Ahead-Guard: prices_df.filter(index <= asof_ts) vor allen Berechnungen"
  - "confidence = n_active_signals / 3 (einfache Ratio, keine Kalibrierung nötig)"
  - "SELL-Trigger: momentum_rank > 80% der Coins (dynamisch, nicht fix auf 8)"
metrics:
  duration: "6 Minuten"
  completed: "2026-06-21"
  tasks_completed: 2
  files_created: 5
  tests_added: 27
  tests_pass: 27
---

# Phase 1 Plan 05: Sizing + SignalService Zusammenfassung

**One-liner:** Vol-Targeting-Sizing (target/vol, cap=1.5) + draw-down-Brake (50%-Halbierung) + SignalVector-Orchestration (Layers 1-3) via `signal_service.evaluate()` mit injiziertem Data-Pattern für DB-freie Tests.

## Was wurde gebaut

### T01 — sizing.py (Layer 3 Sizing)

`backend/application/signals/sizing.py` implementiert drei Funktionen:

- **`vol_target_size(pred_vol, target_vol=0.60, cap=1.5)`**: Formel `target_vol / max(pred_vol, ε)`, gecappt auf `[0, cap]`. Bei `pred_vol ≤ 0` → Safety-Fallback: size = cap. Monoton (höhere Vol → kleinere Size).
- **`drawdown_brake(size, current_dd, threshold=-0.20)`**: Halbiert den Size-Factor wenn `current_dd < threshold`. Grenzfall `current_dd == threshold` → kein Brake.
- **`apply_sizing(action, pred_vol, current_dd=0.0, ...)`**: Pipeline-Funktion. `SELL` → immer `0.0` (niemals Short). Sonst: `vol_target_size()` gefolgt von `drawdown_brake()`.

15 Unit-Tests (A7.5 Monotonizität, A7.8 SELL=0.0, Bounds, Grenzfälle) — alle grün.

### T02 — SignalVector Schema + signal_service.py (Layers 1-3)

`backend/interfaces/rest/schemas/signals.py` definiert:
- **`SignalVector`**: Pydantic-Schema exakt laut CONTEXT.md mit `action: Literal["BUY","HOLD","SELL"]`, `size_factor ∈ [0.0, 1.5]`, `consensus: str`, `sub_scores: dict[str, float]`, `confidence ∈ [0.0, 1.0]`, `disclaimer`.
- **`BacktestReport`**: Schema für Walk-Forward-Backtest-Ergebnisse (Wave 4).

`backend/application/signals/signal_service.py` orchestriert:
1. **Layer 1**: `cross_sectional_momentum()` → `momentum_rank`, `onchain_health_score()` → `onchain_score` (Fallback 0.5)
2. **Layer 2**: `sma(100)` + `rsi(14)` + `macd()` → Binärsignale → `consensus_vote()` → `"N/3"` String
3. **Layer 3**: `predict_vol()` (Fallback 0.60) + `apply_sizing()` → `size_factor`
4. **Look-Ahead-Guard**: `prices_df` auf `asof_date` gefiltert vor allen Berechnungen
5. **Action-Logik**: BUY wenn consensus=1, SELL wenn momentum_rank > 80% der Coins, sonst HOLD

12 Unit-Tests (SignalVector-Rückgabe, sub_scores Keys, SELL→0.0, Pydantic-Validierung, Look-Ahead) — alle grün.

## Abweichungen vom Plan

### Auto-fix: mypy-Typen in vol_forecast.py [Rule 1 - Bug]

**Gefunden:** mypy meldete 2 Fehler in `vol_forecast.py` (Wave 2 Datei) beim Prüfen von `signal_service.py` (transitiv).
- `_oos_r2()` hatte unparametrisierten `np.ndarray`-Typ
- `oos_r2 = lgbm_r2` wo `lgbm_r2: float | None` → Type-Narrowing-Problem

**Fix:** Annotation auf `"np.ndarray[Any, Any]"` geändert; `oos_r2 = lgbm_r2 if lgbm_r2 is not None else har_r2` für explizites Type-Narrowing.

**Commit:** `aa73d3c`

### Deviation: asyncio.get_event_loop() → asyncio.run() [Rule 1 - Bug]

**Gefunden:** Tests verwendeten deprecated `asyncio.get_event_loop().run_until_complete()` (Python 3.10+ deprecation).
**Fix:** `_run(coro)` Hilfsfunktion mit `asyncio.run()` in allen Tests.
**Commit:** `aa73d3c`

### Deviation: SELL-Threshold dynamisch statt fix [Rule 2 - Enhancement]

**Geplant:** `if momentum_rank > 8: action = "SELL"` (fixer Wert für 10-Coin-Universum)
**Implementiert:** `sell_threshold = max(int(n_coins * 0.8), 8)` — dynamisch basierend auf Anzahl Coins. Bleibt bei 10 Coins äquivalent (max(8, 8) = 8), aber robuster für unterschiedliche Universumsgrossen.

## Bekannte Stubs

Keine.

## Threat Flags

Keine neuen sicherheitsrelevanten Oberflächen eingeführt (nur reine Berechnungslogik + Pydantic-Schemas, kein Netzwerk, keine DB, keine Datei-I/O).

## Self-Check

Dateien erstellt:
- `backend/application/signals/sizing.py` — vorhanden
- `backend/application/signals/signal_service.py` — vorhanden
- `backend/interfaces/rest/schemas/signals.py` — vorhanden
- `backend/tests/unit/application/test_sizing.py` — vorhanden
- `backend/tests/unit/application/test_signal_service.py` — vorhanden

Commits vorhanden:
- `e5b509a` test(01-05): RED sizing
- `0944afc` feat(01-05): GREEN sizing
- `51077c6` test(01-05): RED signal_service
- `aa73d3c` feat(01-05): GREEN signal_service
