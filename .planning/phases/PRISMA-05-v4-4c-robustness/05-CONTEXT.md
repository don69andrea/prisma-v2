---
phase: 05-v4-4c-robustness
goal: Robustness/stress-test of the V4-1 Signal Engine over the full Top-10 universe
branch: feat/v4-4b-portfolio
v4_phase: V4-4c
---

# Phase 05 — V4-4c: Robustheits-/Stresstest der V4-1-Engine

## Fragestellung

Hält der Edge aus V4-1 (Trend + Vol-Targeting schlägt exposure-matched Baseline)?

1. Bei **höheren Kosten** (0.1 / 0.2 / 0.5 % RT)?
2. Über das **volle Top-10-Universum** (nicht nur BTC/ETH)?
3. Bei **Parameter-Variation** (MA-Fenster, Vol-Fenster)?

## Scope (lean)

- Ein Script `scripts/robustness_analysis.py` mit synthetischen Daten (kein Live-DB nötig).
- Nutzt existierende `run_walkforward()` und `signal_service.evaluate()`-Logik.
- Ausgabe: JSON-Tabelle Sharpe/Calmar/MaxDD pro Coin × Cost-Level.
- Kein FORTSCHRITT.md-Eintrag in Phase 05 — Ergebnisse fliessen in Phase 06 FORTSCHRITT.

## Kriterien für "robust"

Edge gilt als robust wenn:
- Bei Kosten 0.2 %: Strategie schlägt exposure-matched Baseline für ≥ 7/10 Coins.
- Bei Kosten 0.5 %: Edge-Reduktion dokumentiert aber nicht negativ gewertet.
- Parameter-Variation: Edge-Richtung (Sharpe > Baseline) bleibt in ≥ 8/10 Parameterkombinationen.

## Plan

- 05-01: `scripts/robustness_analysis.py` + Test
