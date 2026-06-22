---
phase: 04-v4-4-rag-sentiment-planned
plan: "07"
subsystem: backtest-sentiment
tags: [backtest, sentiment, d-08, honesty, walk-forward, veto]
dependency_graph:
  requires: ["04-05", "04-06"]
  provides: ["compare_sentiment_backtest", "d06-veto-wiring", "fortschritt-v4-4"]
  affects: ["signal_director", "config", "fortschritt"]
tech_stack:
  added: []
  patterns:
    - "2x walk-forward comparison (DISABLED vs ENABLED) without modifying walkforward.py"
    - "D-06 veto wiring in _synthesize() behind SENTIMENT_ENABLED flag"
    - "sentiment_enabled: bool = False in Settings (pydantic-settings)"
key_files:
  created:
    - scripts/compare_sentiment_backtest.py
    - backend/tests/integration/test_backtest_sentiment_comparison.py
  modified:
    - backend/application/agents/signal_director.py
    - backend/config.py
    - docs/PRISMA_V4_FORTSCHRITT.md
decisions:
  - "D-08: SENTIMENT_ENABLED=false bleibt Standard bis Live-Backtest D-08-Regel erfuellt"
  - "walkforward.py nicht modifiziert (Open Question 3); Veto durch Positions-Zeroing vor dem Walkforward-Call"
  - "D-06-Wiring in signal_director._synthesize() (Rule 2: fehlende kritische Funktionalitaet)"
metrics:
  duration: "~15min"
  completed: "2026-06-22"
  tasks_completed: 2
  tasks_total: 3
  files_created: 2
  files_modified: 3
---

# Phase 04 Plan 07: D-08 Honesty Backtest — Sentiment Comparison Summary

**One-liner:** 2x Walk-forward Vergleich DISABLED/ENABLED mit importierbarer compare_sentiment_backtest()-Funktion, D-06 Veto-Wiring in SignalDirector, und ehrlichem FORTSCHRITT-Abschnitt (Platzhalter bis Live-Run).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | compare_sentiment_backtest.py + Tests | 14d6e6a | scripts/compare_sentiment_backtest.py, test_backtest_sentiment_comparison.py, signal_director.py, config.py |
| 2 | FORTSCHRITT.md V4-4 Sentiment Abschnitt | c7bc444 | docs/PRISMA_V4_FORTSCHRITT.md |

## Checkpoint (Task 3)

Gestoppt bei `checkpoint:human-verify` — Live-Backtest gegen echte DB erforderlich.

## What Was Built

### Task 1: compare_sentiment_backtest.py

- `compare_sentiment_backtest(prices, signals, coin, veto_records, costs, min_train, step) -> ComparisonResult` — importierbare Vergleichsfunktion; ruft `run_walkforward_with_details()` zweimal auf
- `ComparisonResult` dataclass mit disabled_/enabled_ Feldern fuer Sharpe, Calmar, MaxDD, Hit-Rate + vetoed_trade_count, total_trade_count, sentiment_improves (D-08)
- `SentimentVetoRecord` dataclass fuer Veto-Ereignisse per Handelstag
- `_apply_veto_to_positions()` setzt Positionen auf 0 wo Veto aktiv, skaliert Downside per D-06
- Synthetische Demo-Daten fuer Dry-Run ohne DB (`_make_synthetic_prices`, `_make_synthetic_signals`, `_make_synthetic_veto_records`)
- async main() + asyncio.run() Einstiegspunkt (Pattern aus llm_smoke_judge.py)
- `walkforward.py` NICHT modifiziert (Open Question 3 eingehalten)

### D-06 Veto-Wiring (Rule 2 Deviation)

`backend/application/agents/signal_director.py` fehlte das D-06 Veto-Wiring in `_synthesize()`. Ohne dieses Wiring waeren alle Veto-Tests gescheitert. Hinzugefuegt:
- `if _settings.sentiment_enabled and senti.veto: action = "HOLD"`
- `if _settings.sentiment_enabled and senti.score < 0: size_factor = size_factor * (1 + senti.score * 0.3)`

### backend/config.py

`sentiment_enabled: bool = False` hinzugefuegt (liest `SENTIMENT_ENABLED` Env-Var per pydantic-settings).

### Test-Datei (12 Tests, alle gruen)

- `test_comparison_module_importable` — Modul + Funktion importierbar
- `test_comparison_produces_all_four_metrics` — alle 4 Metriken + vetoed_trade_count vorhanden
- `test_veto_zeroes_positions_and_is_counted` — Veto-Records fuehren zu gezaehlten Vetoes
- `test_all_top_coins_produce_results` — BTC/ETH/SOL/BNB/XRP alle durchlaufen
- `test_disabled_equals_enabled_without_veto_records` — ohne Veto: identische Metriken
- 4 async Director-Tests (Veto engaged, disabled no-veto, downside scaling, positive no-amplify)
- 2 VetoedTradeCount-Tests

### Task 2: FORTSCHRITT.md V4-4 Abschnitt

- DISABLED vs. ENABLED Metriktabelle mit [PENDING] Platzhaltern fuer alle 5 Coins
- D-08 Entscheidungsregel explizit dokumentiert
- Veto-Statistik Feld
- Keine Schwellenwert-Optimierung bestaetigt
- Wort "Capstone" erscheint nicht

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] D-06 Veto-Wiring in signal_director._synthesize()**
- **Found during:** Task 1 — Test `test_veto_engaged_on_fear_coins_multi_coin` failed (BNB: HOLD erwartet, BUY erhalten)
- **Issue:** `_synthesize()` in signal_director.py hatte das D-06 Sentiment-Veto und Downside-Skalierungs-Wiring nicht implementiert, obwohl es in PATTERNS.md und CONTEXT.md D-06 beschrieben war
- **Fix:** Veto-Guard (`if _settings.sentiment_enabled and senti.veto: action = "HOLD"`) und Downside-Skalierung (`size_factor *= (1 + senti.score * 0.3)`) hinter `get_settings()` eingefuegt
- **Files modified:** `backend/application/agents/signal_director.py`
- **Commit:** 14d6e6a

**2. [Rule 2 - Missing Critical Functionality] sentiment_enabled in backend/config.py**
- **Found during:** Task 1 — `get_settings()` hatte kein `sentiment_enabled` Feld; AttributeError waere aufgetreten
- **Fix:** `sentiment_enabled: bool = False` zu Settings-Klasse hinzugefuegt
- **Files modified:** `backend/config.py`
- **Commit:** 14d6e6a

## Known Stubs

Die Metriktabelle in `docs/PRISMA_V4_FORTSCHRITT.md` enthaelt `[PENDING — live run required]` Platzhalter fuer alle numerischen Werte. Diese sind intentional: die echten Zahlen entstehen erst nach dem Live-Backtest-Lauf in Task 3 (Human-Verify Checkpoint).

## Threat Flags

Keine neuen Sicherheits-relevanten Surfaces eingefuehrt. Backtest-Skript hat keinen DB-Zugriff und keinen LLM-Call. Das SENTIMENT_ENABLED Flag ist per Default false (sicher).

## Self-Check

- [x] scripts/compare_sentiment_backtest.py existiert
- [x] backend/tests/integration/test_backtest_sentiment_comparison.py existiert (12 Tests, alle gruen)
- [x] backend/application/backtest/walkforward.py NICHT modifiziert
- [x] docs/PRISMA_V4_FORTSCHRITT.md enthaelt V4-4 Sentiment Abschnitt
- [x] "Capstone" erscheint nicht im hinzugefuegten Abschnitt
- [x] Commits 14d6e6a und c7bc444 existieren
- [x] Checkpoint Task 3 korrekt gestoppt

## Self-Check: PASSED
