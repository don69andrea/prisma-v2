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

---

## V4-2 Meta-Labeling — ✅ verifiziert (2026-06-21, Branch feat/v4-2-meta-labeling)

- **Implementiert:** `meta_label.py` — Triple-Barrier-Labels, Trend-Scan-Labels, `build_meta_features` (10 Features, shift(1)), `fit_meta_classifier` (LogReg/LightGBM), `_walkforward_meta_cv` (embargo=5), `predict_meta_label`.
- **Backtest-Integration:** `run_walkforward()` + `run_walkforward_with_details()` um optionalen `meta_filter: pd.Series | None` erweitert (backward-compatible, ML-08 bestanden).
- **Schema:** `MetaLabelReport` (15 Felder inkl. `finding` + `finding_reason`).
- **API:** `GET /api/v1/signals/meta-label/{coin}` via `asyncio.to_thread`.
- **Tests:** 47 grün · meta_label.py Coverage 97.1% · walkforward.py 100% · ruff + mypy sauber.
- **Methodik:** Expanding-Window (min_train=252, step=21, embargo=5). Baseline auf gleichen OOS-Daten. `finding`-Feld: positive/secondary_pass/negative — kein Overfit.
- **Backtest-Zahlen (V4-2):** Keine realen BTC/ETH-Zahlen in dieser Phase — by design. V4-2 liefert die Pipeline (`MetaLabelReport`-Schema, `meta_filter`-Parameter in `run_walkforward`, REST-Endpoint). Reale OOS-Vergleichszahlen (Sharpe/Calmar/Trades WITH vs. WITHOUT meta-filter je Coin) entstehen erst in V4-3+ wenn der Endpoint gegen echte historische Preisdaten (yfinance) betrieben wird. Die Finding-Logik ist vollständig implementiert und über Monkeypatch-Tests auf alle drei Äste (positive/secondary_pass/negative) verifiziert.
