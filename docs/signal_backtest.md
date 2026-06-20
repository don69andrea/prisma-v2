# PRISMA V3 — Phase 3 Signal-Backtest (mit ML Risk-Overlay)

**Stand:** 2026-06-20 · **OOS-Periode:** 2019-01-01 – 2026-06-01
**Spec:** PRISMA_V3_ANNOTATED_v33.md TEIL G / Contract E3 / Kap. 5.1 / Kap. 17

> **Dieses Dokument ersetzt den Floor-Bericht (ohne ML).**
> Vergleich: „Floor" (ml = 50 neutral) vs „ML-Overlay" (crypto-v2 Risk-Gate, p < 0.35).
> ML-Overlay ist ein RISIKO-GATE, kein Return-Prädiktor — ml_score im Gewichtungsschema bleibt 50.

---

## 1 · Methodik

| Parameter | Wert |
|---|---|
| **Signal** | Kombiniertes Signal: quant + ml + macro (TEIL G2-Gewichte) |
| **ML-Overlay** | crypto-v2 LightGBM (Risk-Gate): p < 0.35 → kein Krypto-Signal |
| **Universums** | 8 SMI/SMIM-Titel + BTC + ETH |
| **Signalfrequenz** | Monatlich (1×/Monat pro Titel) |
| **Horizont** | 21 Handelstage (~1 Monat) |
| **OOS** | 2019-01-01 – 2026-06-01 |
| **TC CH-Aktien** | 0.90% Round-Trip |
| **TC Krypto** | 0.50% Round-Trip |
| **Engine** | BacktestEngine (Contract E3), event-getrieben, kein Look-Ahead |
| **Benchmark Aktien** | ^SSMI Buy-and-Hold |
| **Benchmark Krypto** | BTC Buy-and-Hold |

### 1.1 Signal-Aggregation (TEIL G2)

| Komponente | Aktien | Krypto | Datenbasis |
|---|---|---|---|
| **quant_score** | 0.50 | 0.40 | Preis/Technik (Momentum, RSI, Bollinger) |
| **ml_score** | 0.10 | 0.20 | Neutral (50.0) — nicht als Return-Prädiktor |
| **macro_score** | 0.40 | 0.40 | SNB-Rate-Geschichte |
| **ML Risk-Gate** | — | p < 0.35 → blockiert | crypto-v2 (MVRV, Fear&Greed, Tech) |

> **Overlay-Design:** Das Krypto-v2-Modell (LightGBM, FEATURE_HASH=03c3e1b0) sagt p(30d-Return > +2%)
> vorher. Wenn p < 0.35, wird das Signal blockiert (Gefahrenzone). Bei p ≥ 0.35
> entscheidet der kombinierte quant+macro-Score wie gehabt. Die ml_score-Gewichte (0.20 Krypto)
> bleiben auf 50.0 — keine Doppelnutzung des Modells als Return-Prädiktor.
> Features: vol_30d, return_90d, excess_vs_btc_30d, MVRV (Fallback 0.0), drawdown_90d, RSI,
> Bollinger, MACD, Fear&Greed (Fallback 50).

---

## 2 · VORHER/NACHHER — Krypto-Overlay (Kern-Tabelle)

| Metrik | Floor (ml=50) | ML-Overlay (Gate 0.35) | Δ |
|---|---|---|---|
| **N Signale** | 74 | 46 | -28 |
| **Gated Signale** | — | 28 | — |
| **Signal-Rate** | 41% | 26% | — |
| **Win-Rate (netto)** | 47.3% | 73.9% | ▲26.6% |
| **Avg. Net-Return** | +4.2% | +14.4% | ▲10.2% |
| **Avg. Net-Alpha** | +0.4% | +2.3% | ▲1.9% |
| **CAGR** | +4.2% | +222.8% | ▲218.6% |
| **Sharpe** | 0.06 | 1.87 | ▲1.81 |
| **Max-Drawdown** | -65.3% | -23.7% | ▲41.6% |

**BTC Buy-and-Hold:** CAGR=+31.2% · Sharpe=0.61 · MaxDD=-76.6%

---

## 3 · CH-Aktien (unverändert zum Floor)

### 3.1 Gesamtperiode OOS (2019–2026)

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

### 3.2 Walk-Forward Folds

| Fold | N | Win-Rate | Avg. Net | Net-Alpha |
|---|---|---|---|---|
| 2019–20 | 64 | 57.8% | +1.1% | +0.2% |
| 2021–22 | 47 | 46.8% | -1.2% | -1.0% |
| 2023–24 | 5 | 40.0% | -0.6% | -2.1% |
| 2025–26 | 26 | 38.5% | +0.2% | +0.2% |

---

## 4 · Krypto — Vollständige Ergebnisse (Overlay)

### 4.1 Gesamtperiode OOS (2019–2026)

| Metrik | ML-Overlay | BTC Buy-and-Hold |
|---|---|---|
| **N Signale** | 46 (Rate 26%) | — |
| **Win-Rate (netto)** | 73.9% | — |
| **Avg. Net-Return** | +14.4% | — |
| **Avg. Net-Alpha** | +2.3% | — |
| **CAGR** | +222.8% | +31.2% |
| **Sharpe** | 1.87 | 0.61 |
| **Max-Drawdown** | -23.7% | -76.6% |

**Gesamturteil Overlay: ✅ EDGE VORHANDEN** (Floor war: ❌ KEIN EDGE)

### 4.2 Walk-Forward Folds — Overlay vs Floor

| Fold | Overlay N | Win-Rate | Avg. Net | Alpha | Floor N | Floor Win |
|---|---|---|---|---|---|---|
| 2019–20 | 22 | 77.3% | +14.1% | +0.1% | 31 | 58.1% |
| 2021–22 | 16 | 68.8% | +16.1% | +2.8% | 26 | 42.3% |
| 2023–24 | 2 | 100.0% | +2.7% | -6.0% | 5 | 40.0% |
| 2025–26 | 6 | 66.7% | +15.2% | +11.9% | 12 | 33.3% |

---

## 5 · Ehrliche Schlussfolgerungen

### 5.1 Was der Overlay leistet
Der Risk-Gate blockiert Krypto-Signale wenn das Regime-Modell p(up) < 0.35 anzeigt.
Fokus: Drawdown-Schutz in Bärphasen (2022: Modell −27% vs BaH −65.8%, Phase-2-Ergebnis).

### 5.2 Krypto-Interpretation
Overlay reduziert Drawdown gegenüber Floor — der Regime-Filter arbeitet.
Overlay verbessert Sharpe gegenüber Floor (1.87 vs 0.06).

### 5.3 Aktien-Interpretation
Aktien unverändert: ml_score = 50 neutral, kein ML-Gate für Aktien.
Win-Rate < 52% — Edge für Aktien ohne Fundamentals (TEIL F) nicht nachgewiesen.

### 5.4 Nächste Schritte
1. **Aktien-ML-Score aktivieren** (Quantil-Regression Phase 2 Aktien, auf main via registry.json)
2. **stock_price_history befüllen** → SignalAccuracyAgent live
3. **Overlay mit Feature-Granularität debuggen** (MVRV-Verfügbarkeit, Fear&Greed-Gap prüfen)
4. **Threshold-Optimierung** (0.35 vs 0.40/0.45) in Walk-Forward

---

## 6 · Technische Details

- **BacktestEngine:** `backend/application/services/backtest_engine.py` (Contract E3)
- **CryptoMLOverlay:** `backend/application/services/crypto_ml_overlay.py`
- **Modell:** `models/crypto_v2_dir_2026-06-20.joblib` (FEATURE_HASH=03c3e1b0)
- **Gate-Schwelle:** p < 0.35 (Danger-Zone-Only, kein Return-Score)
- **Deterministisch:** gleiche Inputs → gleiche Ergebnisse

---

*PRISMA V3 Phase 3 Signal-Backtest · 2026-06-20 · Andrea Petretta · FHNW BI Modul FS 2026*
