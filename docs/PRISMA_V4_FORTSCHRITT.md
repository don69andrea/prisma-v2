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

---

## V4-2 Nachbefund: Meta-Label OOS-Eval — ⚠️ NEGATIV (2026-06-21, Branch feat/v4-2-meta-eval)

**Fragestellung:** Verbessert der Meta-Filter die risiko-adjustierte Performance (Sharpe + Calmar) oder senkt er nur Trades/Kosten?

**Methodik:** Expanding-Window Walk-Forward gegen echte yfinance-Daten (BTC-USD, ETH-USD, BNB-USD, SOL-USD), 2019-01-01 – 2024-12-31. min_train=252, step=21, embargo=5. Kosten 0.1% netto. OOS-Periode: 1428–1890 Bars je Coin (90 bzw. 68 Folds). Skript: `scripts/meta_label_eval.py`.

**Ergebnisse (MIT vs. OHNE Meta-Filter, OOS-Periode):**

| Coin    | Sharpe OHNE | Sharpe MIT | Δ Sharpe | Calmar OHNE | Calmar MIT | Δ Calmar | MaxDD OHNE | MaxDD MIT  | Trades OHNE | Trades MIT | Befund     |
|---------|-------------|------------|----------|-------------|------------|----------|------------|------------|-------------|------------|------------|
| BTC-USD | 1.093       | 0.921      | −0.172   | 0.780       | 0.651      | −0.129   | −50.6%     | −42.7%     | 168         | 202        | SCHLECHTER |
| ETH-USD | 0.888       | 0.935      | +0.047   | 0.586       | 0.811      | +0.225   | −64.0%     | −44.7%     | 176         | 184        | BESSER     |
| BNB-USD | 1.056       | 0.777      | −0.280   | 0.869       | 0.477      | −0.392   | −66.8%     | −68.6%     | 186         | 214        | SCHLECHTER |
| SOL-USD | 1.387       | 1.504      | +0.117   | 1.559       | 2.053      | +0.495   | −71.0%     | −57.0%     | 150         | 142        | BESSER     |

**Analyse:**
- 2/4 Coins (ETH, SOL) zeigen Verbesserung in Sharpe + Calmar; 2/4 (BTC, BNB) verschlechtern sich.
- Bei BTC und BNB erhöht der Filter die Trades-Zahl (mehr Filter-Fluktuationen = mehr Kosten, kein Mehrwert).
- Bei ETH und SOL reduziert der Filter den MaxDD substanziell (+19% bzw. +14%), mit marginalem CAGR-Verlust.
- Kein konsistentes Muster über alle Coins — die LogReg-Precision liegt nahe 0.5, der Filter ist rauschbehaftet.

**Gesamtbefund: NEGATIV**
Der Meta-Filter verbessert Sharpe + Calmar nicht konsistent über alle Coins.
**Konsequenz: Meta-Label standardmäßig AUS. Kein belegter Mehrwert. Nicht überoptimieren.**
Die Pipeline bleibt als optionaler Parameter (`meta_filter=None` Default) erhalten — aktivierbar je Coin wenn zukünftige Daten einen stabilen Mehrwert zeigen.
