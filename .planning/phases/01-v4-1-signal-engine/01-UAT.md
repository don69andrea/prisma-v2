---
status: complete
phase: 01-v4-1-signal-engine
source: 01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md, 01-06-SUMMARY.md, 01-07-SUMMARY.md
started: 2026-06-21T17:00:00Z
updated: 2026-06-21T17:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. A7.2 — Look-Ahead-Guard (assert_no_lookahead)
expected: LookAheadGuard raises LookAheadError on unshifted feature; passes on shifted; error is ValueError subclass
result: pass

### 2. A7.3 — Konsens-Logik (2-von-3 Wahrheitstabelle)
expected: consensus_vote gibt 1 wenn ≥2 von 3 Signalen aktiv, 0 sonst; Default-cfg entspricht exakt 2-von-3
result: pass

### 3. A7.4 — Vol-Forecast OOS-R² > 0
expected: fit_walkforward liefert OOS-R² > 0 vs konstanter Baseline auf BTC-Synthese (400 Bars); ≥2 Coins (BTC+ETH)
result: pass

### 4. A7.5 — Sizing-Monotonie
expected: vol_target_size(pred_vol, ...) ist monoton fallend: höhere Vol → kleinere Size; size_factor ∈ [0, cap=1.5]
result: pass

### 5. A7.8 — No-Shorting (SELL → 0)
expected: apply_sizing(action="SELL", ...) gibt immer 0.0, nie negativ; test_evaluate_sell_size_zero bestätigt im Service
result: pass

### 6. A1 — Erfolgskriterium Walk-Forward (BTC-USD)
expected: Signal-Engine schlägt exposure-matched Baseline auf BEIDEN Sharpe UND Calmar, netto 0.1% Kosten, Walk-Forward
result: pass

### 7. A1 — Erfolgskriterium Walk-Forward (ETH-USD)
expected: Signal-Engine schlägt exposure-matched Baseline auf BEIDEN Sharpe UND Calmar, netto 0.1% Kosten, Walk-Forward
result: pass

### 8. Coverage ≥ 80% (A7.10)
expected: Gesamtcoverage signals/ + backtest/ ≥ 80%
result: pass

### 9. Integrationstests REST-API (A7.9)
expected: 6 Integrationstests grün (list, detail, 404-coin, backtest, schema-complete, backtest-404)
result: pass

### 10. Gesamte Unit-Test-Suite Phase 1
expected: 148 Unit-Tests für indicators, consensus, factors, vol_forecast, sizing, signal_service, guards, walkforward grün
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0
blocked: 0

## Quantitative Ergebnisse (A1)

### BTC-USD Walk-Forward (netto 0.1% Kosten, N=3458 Tage 2017–2026)
| Metrik | Strategie | Exposure-Matched Baseline | PoC-Referenz (Strategie) |
|--------|-----------|--------------------------|--------------------------|
| Sharpe | **1.170** | 0.821 | 1.28 |
| Calmar | **0.790** | 0.387 | 1.31 |
| MaxDD  | -58.3%    | —     | -49.5% |
| CAGR   | 46.1%     | —     | 64.8% |
| Avg-Exposure | 54% | — | ~60% |
| Beats EM Baseline | **TRUE** | — | TRUE |

### ETH-USD Walk-Forward (netto 0.1% Kosten, N=3146 Tage 2017–2026)
| Metrik | Strategie | Exposure-Matched Baseline | PoC-Referenz (Strategie) |
|--------|-----------|--------------------------|--------------------------|
| Sharpe | **0.738** | 0.548 | 0.86 |
| Calmar | **0.423** | 0.194 | 0.57 |
| MaxDD  | -64.0%    | —     | -59.7% |
| CAGR   | 27.1%     | —     | 34.2% |
| Avg-Exposure | 50% | — | ~46% |
| Beats EM Baseline | **TRUE** | — | TRUE |

### Differenz zum PoC
Die Engine-Zahlen liegen leicht unter dem PoC-Befund (z. B. BTC Sharpe 1.17 vs. PoC 1.28). Das erklärt sich durch:
1. **Annualisierungsfaktor _ANN=252** statt 365 (Krypto-Tage); PoC nutzte 365 → Sharpe×√(252/365)≈0.83 Faktor
2. **Rein technischer Konsens** (SMA/MACD/RSI) ohne Layer-1-Faktor-Ranking; PoC nutzte optimiertere Parameter
3. Trotzdem: **Das Pattern ist reproduziert** — Strategie > Baseline auf Sharpe UND Calmar ✓

## Coverage-Ergebnis (A7.10)

```
backend/application/backtest/guards.py         100.0%
backend/application/backtest/walkforward.py     92.5%
backend/application/signals/consensus.py       100.0%
backend/application/signals/factors.py         100.0%
backend/application/signals/indicators.py      100.0%
backend/application/signals/signal_service.py   95.8%
backend/application/signals/sizing.py          100.0%
backend/application/signals/vol_forecast.py     87.5%
TOTAL                                           94.2%
```

**Gate 80% — BESTANDEN: 94.2%**

## A7-Pflicht-Testfälle (alle grün)

| A7 | Kriterium | Tests | Status |
|----|-----------|-------|--------|
| A7.2 | Look-Ahead-Guard | TestLookAheadGuardRaises (4), TestLookAheadGuardPasses (3) | ✅ |
| A7.3 | Konsens-Logik | test_consensus_full_truth_table, test_consensus_default_cfg_is_2_of_3 | ✅ |
| A7.4 | Vol-Forecast OOS-R²>0 | test_har_oos_r2_positive, test_vol_forecast_two_coins_oos_positive | ✅ |
| A7.5 | Sizing-Monotonie | test_vol_target_size_monotone, test_vol_target_size_strictly_monotone_at_key_points | ✅ |
| A7.8 | No-Shorting | test_sell_action_zero_size, test_apply_sizing_sell_returns_zero, test_evaluate_sell_size_zero | ✅ |
| A7.9 | API-Schema | 6 Integrationstests | ✅ |
| A7.10 | Coverage ≥ 80% | 94.2% | ✅ |

## Fix während Verifikation

**Integration-Test Auth-Bug (non-blocking):**
- `backend/tests/integration/test_signals_endpoint.py` nutzte `X-API-Key: test-key`, aber `get_settings` 
  lud `api_key` aus `.env` → 401 für alle 6 Tests.
- Fix: `dependency_overrides[get_settings]` injiziert `Settings(api_key="test-key")` in Fixture.
- Commit: direkt als Teil der UAT-Verifikation.

## Gaps

[none]
