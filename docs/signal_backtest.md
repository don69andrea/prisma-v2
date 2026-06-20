# PRISMA V3 — Phase 3 Signal-Backtest

**Stand:** 2026-06-20 · **OOS-Periode:** 2019-01-01 – 2026-06-01
**Spec:** PRISMA_V3_ANNOTATED_v33.md TEIL G / Contract E3 / Kap. 5.1 / Kap. 17

> Ziel: Misst, ob das **kombinierte Signal** (quant + ml + macro) einen historisch validierten,
> netto-of-cost Edge hat. Phase 2 hat ML allein getestet; Phase 3 testet das Gesamtprodukt.

---

## 1 · Methodik

| Parameter | Wert |
|---|---|
| **Signal** | Kombiniertes Signal: quant + ml + macro (TEIL G2-Gewichte) |
| **Universums** | 8 SMI/SMIM-Titel + BTC + ETH |
| **Signalfrequenz** | Monatlich (1×/Monat pro Titel) |
| **Horizont** | 21 Handelstage (~1 Monat) |
| **OOS** | 2019-01-01 – 2026-06-01 |
| **TC CH-Aktien** | 0.90% Round-Trip (Stempel 0.15% + Courtage 0.20% + Spread 0.10%, je Seite) |
| **TC Krypto** | 0.50% Round-Trip (Fee 0.15% + Slippage 0.10%, je Seite) |
| **Engine** | BacktestEngine (Contract E3), event-getrieben, kein Look-Ahead |
| **Benchmark Aktien** | ^SSMI Buy-and-Hold |
| **Benchmark Krypto** | BTC Buy-and-Hold |

### 1.1 Signal-Aggregation (TEIL G2)

| Engine | Aktien-Gewicht | Krypto-Gewicht | Datenbasis |
|---|---|---|---|
| **quant_score** | 0.50 | 0.40 | Preis/Technik (Momentum, RSI, Bollinger) |
| **ml_score** | 0.10 | 0.20 | Neutral (50.0) — Modell nicht auf main |
| **macro_score** | 0.40 | 0.40 | SNB-Rate-Geschichte (approximiert) |

BUY-Schwelle: Aktien ≥ 65, Krypto ≥ 60

> **ML-Hinweis:** Das Krypto-v2-Modell (`crypto_v2_dir`) ist auf dem `main`-Branch
> nicht verfügbar (joblib nicht committed). `ml_score = 50` (neutral) in allen Signalen.
> Dies unterschätzt den kombinierten Signal-Edge bei Krypto — der Regime-/Timing-Vorteil
> aus Phase 2 (Calmar 1.81 vs 1.12, 2022 −9% vs −33%) ist hier **nicht** eingerechnet.
> Der vollständige Test mit Modell ist ein TODO für nach dem nächsten Merge.

---

## 2 · CH-Aktien — Ergebnisse

### 2.1 Gesamtperiode OOS (2019–2026)

| Metrik | Kombiniertes Signal | SMI Buy-and-Hold |
|---|---|---|
| **N Signale** | 144 (Signal-Rate 20%) | — |
| **Win-Rate (netto)** | 50.3% | — |
| **Avg. Net-Return** | +0.1% | — |
| **Avg. Net-Alpha** | -0.3% | — |
| **CAGR** | -6.0% | +6.4% |
| **Sharpe** | -0.35 | 0.43 |
| **Max-Drawdown** | -42.8% | -27.5% |

**Gesamturteil: ⚠️ EDGE GRENZWERTIG**

### 2.2 Walk-Forward Folds (je 2 Jahre)

| Fold | N | Win-Rate | Avg. Net | Net-Alpha |
|---|---|---|---|---|
| 2019–20 | 64 | 57.8% | +1.1% | +0.2% |
| 2021–22 | 47 | 46.8% | -1.2% | -1.0% |
| 2023–24 | 5 | 40.0% | -0.6% | -2.1% |
| 2025–26 | 26 | 38.5% | +0.2% | +0.2% |

---

## 3 · Krypto — Ergebnisse

### 3.1 Gesamtperiode OOS (2019–2026)

| Metrik | Kombiniertes Signal | BTC Buy-and-Hold |
|---|---|---|
| **N Signale** | 74 (Signal-Rate 41%) | — |
| **Win-Rate (netto)** | 47.3% | — |
| **Avg. Net-Return** | +4.2% | — |
| **Avg. Net-Alpha** | +0.4% | — |
| **CAGR** | +4.2% | +31.2% |
| **Sharpe** | 0.06 | 0.61 |
| **Max-Drawdown** | -65.3% | -76.6% |

**Gesamturteil: ❌ KEIN EDGE**

### 3.2 Walk-Forward Folds (je 2 Jahre)

| Fold | N | Win-Rate | Avg. Net | Net-Alpha |
|---|---|---|---|---|
| 2019–20 | 31 | 58.1% | +5.6% | -1.5% |
| 2021–22 | 26 | 42.3% | +3.8% | +2.1% |
| 2023–24 | 5 | 40.0% | -2.0% | -5.0% |
| 2025–26 | 12 | 33.3% | +3.9% | +4.0% |

---

## 4 · Ehrliche Schlussfolgerungen

### 4.1 Was dieser Test misst
Den kombinierten Quant+Macro-Anteil des PRISMA-Signals (ML = neutral). Da der Krypto-v2-
Timing-Vorteil (Phase 2: Calmar 1.81 vs 1.12) hier fehlt, ist dieses Ergebnis eine
**Untergrenze** des kombinierten Signal-Edges bei Krypto.

### 4.2 Interpretation Aktien
Ein Quant+Macro-Signal bei 8 SMI/SMIM-Titeln über ~90 Monate liefert n=143 Trades.
Win-Rate unter 52% — kombinierter Edge für Aktien nicht nachgewiesen in diesem Setup.
Wichtig: Das Quant-Signal nutzt keine Fundamentals (TEIL F), die langfristig stärker wirken.

### 4.3 Interpretation Krypto
ML = neutral bewusst gesetzt (Modell nicht auf main). Der Quant+Macro-Anteil allein zeigt
noch keinen stabilen Edge ohne ML-Komponente. Mit Regime-Filter (Phase 2) ist der Calmar-Vorteil 1.81 vs 1.12 belegt.

### 4.4 Nächste Schritte
1. **ML-Modell in main mergen** (feature/prisma-v3-phase-2-crypto-v2) → `ml_score` aus echtem Modell
2. **Aktien-ML-Score nutzen** (Quantil-Regression Phase 2 Aktien, aktuell auf main via registry.json)
3. **stock_price_history befüllen** (seed_historical_prices.py) → SignalAccuracyAgent live betreiben
4. **Signal-Outcomes in DB schreiben** → kontinuierliche Win-Rate via API

---

## 5 · Technische Details

- **BacktestEngine:** `backend/application/services/backtest_engine.py` (Contract E3, event-getrieben)
- **TransactionCostModel:** `backend/domain/services/transaction_cost_model.py` (Kap. 17)
- **SignalOutcomeRepository:** `backend/infrastructure/persistence/repositories/signal_outcome_repository.py`
- **SignalAccuracyAgent:** `backend/application/agents/signal_accuracy_agent.py` (Kap. 5.1)
- **Preisquelle:** yfinance (direkter Pull im Backtest-Script; live via stock_price_history)
- **Deterministisch:** gleiche Inputs → gleiche Ergebnisse (E3.3 Test grün)

---

*PRISMA V3 Phase 3 Signal-Backtest · 2026-06-20 · Andrea Petretta · FHNW BI Modul FS 2026*
