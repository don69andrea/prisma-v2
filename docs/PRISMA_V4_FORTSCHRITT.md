# PRISMA V4 — Fortschritts-Log (append-only)

> Ein Eintrag je verifizierter Phase. Chronologisch, nie rückwirkend ändern.
> Quelle der Wahrheit: PRs auf `develop`, UAT-Reports in `.planning/phases/`.

---

## V4-1 Signal-Engine — ✅ verifiziert (2026-06-21, PR #296)

- **A1-Erfolgskriterium OOS bestanden:** Engine schlägt exposure-matched Baseline auf Sharpe UND Calmar.
  - BTC: Calmar 0.79 vs 0.39 · Sharpe 1.17 vs 0.82
  - ETH: Calmar 0.42 vs 0.19 · Sharpe 0.74 vs 0.55
- 178 neue Tests grün · Coverage 94.2% · Look-Ahead-Guard grün.
- **Bedeutung:** erster belegter POSITIVER Befund des Projekts (V3 war Negativbefund).
- Gelieferte Komponenten: `signals/indicators.py`, `signals/consensus.py`, `signals/vol_forecast.py`,
  `signals/sizing.py`, `signals/signal_service.py`, `signals/factors.py`;
  `backtest/walkforward.py`, `backtest/guards.py`;
  Migrationen 0037–0040; REST-Endpunkte `/api/v1/signals/`.
