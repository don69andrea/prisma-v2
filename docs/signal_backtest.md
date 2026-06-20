# PRISMA V3 — Phase 3 Backtest (Saubere Methodik)

**Stand:** 2026-06-20 · **OOS:** 2019-01-01 – 2026-06-01 (7.4 Jahre)
**Spec:** PRISMA_V3_ANNOTATED_v33.md TEIL G / Contract E3 / Kap. 5.1 / Kap. 17

> **Methodik-Korrekturen gegenüber Vorversion:**
> 1. Walk-Forward: 5 Expanding-Window-Folds — kein Final-Modell, kein Look-Ahead
> 2. Gate-Schwelle p<0.5 (Phase-2-Standard, nicht a posteriori gewählt)
> 3. CAGR/Sharpe über volle OOS-Periode (7.5 Jahre, inkl. Monate ohne Trades)

---

## 1 · Methodik

| Parameter | Wert |
|---|---|
| **WF-Gate** | 5 Expanding-Window LightGBM-Folds (Retrain vor OOS) |
| **Gate-Schwelle** | p < 0.5 (Phase-2-Standard, vorab fixiert) |
| **Gate-Features** | 13 (vol, return, RSI, Bollinger, MVRV, Fear&Greed, MACD) |
| **Training-Daten** | yfinance BTC-USD/ETH-USD + alternative.me + CoinMetrics |
| **Embargo** | 30 Tage (= Horizont) |
| **CAGR-Basis** | 7.41 Jahre (volle OOS-Periode) |
| **Sharpe-Basis** | Alle 90 OOS-Monate (0% für Monate ohne Trade) |
| **TC Krypto** | 0.50% Round-Trip |
| **Benchmark** | BTC Buy-and-Hold |

---

## 2 · VORHER/NACHHER — Saubere Methodik vs Floor vs Fehlerhafter Overlay

| Metrik | Floor (ml=50) | **Honest WF (diese Tabelle)** | ~~Fehlerhafter Overlay~~ |
|---|---|---|---|
| **N Signale** | 74 | 25 | ~~46~~ |
| **Gate-Logik** | keiner | WF-Retrain p<0.5 | ~~Final-Modell p<0.35~~ |
| **Win-Rate** | 47.3% | **44.0%** | ~~73.9%~~ |
| **Avg. Net** | +4.2% | **+1.5%** | ~~+14.4%~~ |
| **Avg. Alpha** | +0.4% | **+0.0%** | ~~+2.3%~~ |
| **CAGR** | +4.2% | **-4.1%** | ~~+222%~~ (Bug) |
| **Sharpe** | 0.06 | **0.01** | ~~1.87~~ (Bug) |
| **Max-Drawdown** | -65.3% | **-67.5%** | ~~-23.7%~~ |

**BTC Buy-and-Hold:** CAGR=+48.3% · Sharpe=0.95 · MaxDD=-76.6%

**Fehlerhafter Overlay war ungültig:** Look-Ahead (Final-Modell auf OOS) + CAGR-Bug (n_years=aktive_Monate/12 statt 7.5) + implizite Schwellen-Wahl.

---

## 3 · Krypto — Vollständige Ergebnisse (WF-Gate)

### 3.1 Gesamtperiode

| Metrik | WF-Gate (p<0.5) | BTC Buy-and-Hold |
|---|---|---|
| **N Signale** | 25 | — |
| **Gated** | 49 von 74 (quant≥60) | — |
| **Aktive Monate** | 19 von 90 | — |
| **Win-Rate** | 44.0% | — |
| **Avg. Net-Return** | +1.5% | — |
| **Avg. Net-Alpha** | +0.0% | — |
| **CAGR (7.5 Jahre)** | -4.1% | +48.3% |
| **Sharpe (90 Monate)** | 0.01 | 0.95 |
| **Max-Drawdown** | -67.5% | -76.6% |

**Gesamturteil: ❌ KEIN EDGE**

### 3.2 Walk-Forward Folds (WF vs Floor)

| Fold | WF N | Win-Rate | Avg.Net | Alpha | Floor N | Floor Win |
|---|---|---|---|---|---|---|
| 2019–20 | 5 | 80.0% | +15.0% | -2.1% | 31 | 58.1% |
| 2021–22 | 10 | 20.0% | -7.3% | -0.0% | 26 | 42.3% |
| 2023–24 | 4 | 50.0% | -1.8% | -6.1% | 5 | 40.0% |
| 2025–26 | 6 | 50.0% | +7.2% | +6.0% | 12 | 33.3% |

---

## 4 · CH-Aktien (unverändert, ohne ML-Gate)

| Metrik | Kombiniertes Signal | SMI BaH |
|---|---|---|
| **N Signale** | 144 | — |
| **Win-Rate** | 50.3% | — |
| **Avg. Net** | +0.1% | — |
| **CAGR** | -3.4% | +6.3% |
| **Sharpe** | -0.23 | 0.42 |
| **MaxDD** | -42.8% | -27.5% |

**Gesamturteil Aktien: ⚠️ GRENZWERTIG**

---

## 5 · Ehrliche Schlussfolgerungen

### 5.1 Was korrigiert wurde
- **Look-Ahead**: 5 Expanding-Window Folds, jeder Fold trainiert nur auf Daten vor dem OOS-Zeitraum
- **CAGR/Sharpe**: n_years = 7.5 (volle OOS-Periode). Sharpe aus allen 90 Monaten inkl. Nullrendite-Monate
- **Schwelle**: p<0.5 (Phase-2-Standard, nicht nachträglich gewählt)

### 5.2 Interpretation

**Ergebnis: WF-Gate bringt keinen messbaren Edge auf monatlicher Granularität.**

Fold-Analyse:
- **Fold 1 (2019–20):** Gate lässt nur 5 von 31 Floor-Signalen durch (p_mean=0.122 → Modell trainiert auf Bärmarkt 2018, prediziert fast alles als "down"). Diese 5 Signale trafen die 2019-Erholungsphase gut (Win=80%, +15.0%) — aber N=5 ist statistisch wertlos.
- **Fold 2 (2021–22):** 10 Signale, Win=20%, Avg.Net=-7.3% — schlechtester Fold, dominiert das Gesamtergebnis. 2021-Bullsignale wurden durch, 2022-Crash traf alle.
- **Fold 3+4 (2022–26):** Neutral bis leicht positiv, keine klare Verbesserung gegenüber Floor.

**Strukturelles Problem:** Der WF-Expanding-Window hat immer das jüngste Bärperiode am Ende des Trainingsfensters (2018 für Fold 1, 2022 für Fold 4). Das Modell lernt "alles fällt" und blockiert die darauffolgende Erholungsphase — Anti-Momentum-Bias.

**Statistische Power:** 25 Trades (vs 74 Floor) über 7.5 Jahre sind zu wenig für robuste Schlüsse. Konfidenzintervall des Win-Rate bei N=25 liegt bei ±20 Prozentpunkten.

**Vergleich Phase-2:** Phase-2 OOS Sharpe = 0.91 auf täglich generierten Signalen, 6 Coins, ~16k Training-Samples. Hier: monatliche Signale, 2 Coins, 910–5246 Training-Samples. Andere Aufgabe, andere Datenlage.

**Schlussfolgerung:** Der fehlerhaftige Overlay (Sharpe 1.87, CAGR +222%) war durch drei Artefakte vollständig erklärt. Nach Korrektur verbleibt kein messbarer Edge des ML-Gate auf dieser Granularität. Das ist ein ehrliches, dokumentierbares Ergebnis.

### 5.3 Nächste Schritte
1. Phase-2-Modell in main mergen → Live-Gate ohne yfinance-Retrain
2. Aktien-ML-Score aktivieren (Quantil-Regression)
3. stock_price_history befüllen → SignalAccuracyAgent live

---

## 6 · Technische Details

- **WF-Training:** yfinance BTC-USD/ETH-USD, MVRV (CoinMetrics), Fear&Greed (alternative.me)
- **Embargo:** 30d (= Horizont), identisch zu Phase-2
- **Gate-Schwelle:** p<0.5 (vorab fixiert)
- **CAGR-Formel:** equity_end^(1/7.497) − 1
- **Sharpe-Formel:** mean(r_all_months) / std(r_all_months) × √12 (n=90 Monate)

---

*PRISMA V3 Phase 3 (saubere Methodik) · 2026-06-20 · Andrea Petretta · FHNW BI Modul FS 2026*
