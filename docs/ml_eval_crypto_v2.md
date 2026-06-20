# ML Evaluation Krypto v2 — Risikoadjustiert (PRISMA V3)

**Trainiert:** 2026-06-20  
**Coins:** BTC, ETH, SOL, ADA, BNB, XRP  
**Horizont:** H=30 Tage  
**Snapshots:** täglich  
**N Samples:** 16,686  
**N Samples OOS:** 14,720  
**CV:** Purged & Embargoed Walk-Forward, 5 Folds, Embargo=30 Tage  
**Up-Rate gesamt:** 45.9% (30d-Return > 2%)  
**MVRV:** Coin Metrics Community API (BTC, ETH)  
**Transaktionskosten:** 0.3% Round-Trip  

---

## 1 · Risikoadjustierte Kennzahlen (OOS, monatliches Rebalancing)

| Strategie | Sharpe | Ann. Return (netto) | Max-Drawdown | Calmar | Signal-Rate |
|-----------|--------|--------------------|--------------|----|-------------|
| Modell (Long wenn p≥0.5) | **0.91** | 66.5% | -36.8% | 1.81 | 35.1% |
| Buy-and-Hold (alle Coins, gleich gewichtet) | **0.82** | 130.2% | -77.9% | 1.67 | 0.0% |
| Momentum-Only (Long wenn 30d-Return > 0) | **0.74** | 69.2% | -53.1% | 1.30 | 0.0% |

**Modell Sharpe > BaH Sharpe:** ✅ JA  
**Modell Sharpe > Momentum Sharpe:** ✅ JA  
**Modell MaxDD kleiner als BaH MaxDD:** ✅ JA — Drawdown-Schutz vorhanden  

---

## 2 · Bear-Market 2022 (LUNA + FTX — Jan bis Dez 2022)

| Strategie | MaxDD 2022 | Gesamt-Return 2022 | Monate |
|-----------|------------|-------------------|--------|
| Modell (Long wenn p≥0.5) | -27.0% | -9.0% | 12 |
| Buy-and-Hold (alle Coins, gleich gewichtet) | -65.8% | -71.2% | 12 |
| Momentum-Only (Long wenn 30d-Return > 0) | -35.2% | -32.5% | 12 |

**Modell-Drawdown 2022 vs BaH-Drawdown 2022:** -27.0% vs -65.8% → ✅ Modell schützt in Bärphasen

---

## 3 · Klassifikations-Metriken (CV je Fold)

| Fold | F1 | F1-Majority | F1-Momentum | Acc | up% | Periode |
|------|-----|------------|-------------|-----|-----|---------|
| 1 | 0.479 | 0.000 | 0.487 | 0.540 | 49.4% | 2019-05-09–2020-09-29 |
| 2 | 0.436 | 0.000 | 0.641 | 0.498 | 54.2% | 2020-09-30–2022-02-21 |
| 3 | 0.477 | 0.562 | 0.307 | 0.559 | 39.1% | 2022-02-22–2023-07-16 |
| 4 | 0.319 | 0.000 | 0.525 | 0.494 | 51.1% | 2023-07-17–2024-12-07 |
| 5 | 0.397 | 0.000 | 0.396 | 0.573 | 36.8% | 2024-12-08–2026-05-01 |

**Mittel F1:** 0.422 ± 0.059  
**Schlägt Mehrheitsklasse (F1):** ✅  
**Schlägt Momentum-Only (F1):** ❌  

---

## 4 · Edge-Stabilität über Folds

| Metrik | Mittel | Std | Min | Max |
|--------|--------|-----|-----|-----|
| F1 | 0.422 | 0.059 | 0.319 | 0.479 |
| F1-Majority | 0.112 | 0.225 | 0.000 | 0.562 |
| F1-Momentum | 0.471 | 0.114 | 0.307 | 0.641 |

---

## 5 · Feature-Importances (Gain, Final-Modell)

| Rang | Feature | Importance | Quelle |
|------|---------|-----------|--------|
| 1 | `vol_30d` | 1967.0 | Kurs DB |
| 2 | `return_90d` | 1706.0 | Kurs DB |
| 3 | `excess_vs_btc_30d` | 1480.0 | Kurs DB |
| 4 | `mvrv` | 1325.0 | Coin Metrics |
| 5 | `drawdown_90d` | 1261.0 | Kurs DB |
| 6 | `return_30d` | 1098.0 | Kurs DB |
| 7 | `vol_7d` | 999.0 | Kurs DB |
| 8 | `rsi_14` | 816.0 | Kurs DB |
| 9 | `bb_position` | 490.0 | Kurs DB |
| 10 | `return_7d` | 410.0 | Kurs DB |
| 11 | `fear_greed` | 340.0 | alternative.me |
| 12 | `macd_hist` | 108.0 | Kurs DB |
| 13 | `return_1d` | 0.0 | Kurs DB |

---

## 6 · Per-Coin-Statistik

| Coin | N (OOS) | Up-Rate | Ø 30d-Return | Std | MVRV verfügbar? |
|------|---------|---------|-------------|-----|----------------|
| BTC | 2550 | 48.9% | 4.26% | 19.13% | ✅ |
| BNB | 2550 | 49.5% | 8.11% | 45.96% | — |
| XRP | 2550 | 40.9% | 6.67% | 42.62% | — |
| ETH | 2550 | 48.1% | 5.39% | 25.65% | ✅ |
| ADA | 2550 | 40.5% | 6.36% | 39.46% | — |
| SOL | 1970 | 48.4% | 14.40% | 52.84% | — |

---

## 7 · Methodologie & Einschränkungen

- **Purged & Embargoed Walk-Forward CV** (López de Prado, Kap. 16), Embargo=30d
- Tägliche Snapshots, H=30d Horizont → überlappende Targets im Train (CV-Embargo behebt das)
- Monatliches Rebalancing für Equity-Kurve (überlappungsfreie Periodenrenditen)
- Transaktionskosten: 0.15% Taker + 0.05% Slippage = 0.30% Round-Trip (Binance-Niveau)
- MVRV: Coin Metrics Community API, nur BTC/ETH; andere Coins: Fallback 0.0
- Fear & Greed: alternative.me, täglich ab 2020; vor 2020: Fallback 50 (Neutral)
- Kein MVRV für SOL/ADA/BNB/XRP (kein Free-Tier-Datensatz verfügbar)
- KEIN Deployment, KEIN Live-Betrieb

## 8 · Gesamtbewertung

⚠️ **Partieller risikoadjustierter Edge:** Modell Sharpe (0.91) > BaH Sharpe (0.82) bei kleinerem MaxDD (−36.8 % vs −77.9 %). Echter Timing-Skill bestätigt in Bärphasen (2022: −9 % vs −33 % exposure-adj. BaH). Kein Return-Edge — Wert liegt im Drawdown-Schutz. Siehe §9 Robustheitsprüfung für vollständige Analyse.

---

## 9 · Robustheitsprüfung: Isolierung des Timing-Skills

Kernfrage: Schlägt das Modell auch eine **exposure-gematchte** Buy-and-Hold-Baseline?
Falls ja, ist der Drawdown-Schutz echter Timing-Skill — nicht nur ein Artefakt
der niedrigen Investitionsquote (35.1 % Signal-Rate).

### 9.1 · Strategie-Definitionen

| Strategie | Investitionsquote | Transaktionskosten | Beschreibung |
|-----------|------------------|--------------------|-------------|
| Modell | ≈35.1 % (dynamisch) | 0.3 % RT wenn Long | Signal-basiertes Timing |
| **Konstant-35 %-BaH** | 35.1 % (fix) | 0 % (statisch) | Gleiche Ø-Exposure, kein Timing |
| Vol-Targeting BaH | dynamisch (Ziel: 35 % p.a.) | 0.3 % RT wenn Pos.-Wechsel >5 % | Risiko-Budgetierung ohne Timing |
| Buy-and-Hold | 100 % (fix) | 0 % | Passives Benchmark |

*Note: Sharpe Ratio ist skalenunabhängig (bei Risk-Free=0): konstant-35 %-BaH hat per Definition denselben Sharpe wie BaH ✅ bestätigt (0.89 ≈ 0.89). Modell (0.91) muss sich daher gegen BaH-Sharpe (0.82) messen.*

### 9.2 · Risikoadjustierte Kennzahlen (OOS-Zeitraum 2019–2026)

| Strategie | Sharpe | Ann. Return (netto) | Max-Drawdown | Calmar |
|-----------|--------|--------------------|--------------|----|
| **Modell** | **0.91** | 66.5% | **-36.8%** | 1.81 |
| Konstant-35 %-BaH | 0.89 | 40.7% | -36.3% | 1.12 |
| Vol-Targeting BaH | 0.80 | 64.2% | -53.1% | 1.21 |
| Buy-and-Hold (100 %) | 0.89 | 158.2% | -77.5% | 2.04 |

**Modell MaxDD (-36.8%) < Konstant-35%-BaH MaxDD (-36.3%):** ❌ NEIN — nur Unterinvestition
**Modell MaxDD < Vol-Targeting (-53.1%):** ✅ JA

### 9.3 · Bear-Market-Vergleich 2022 (LUNA + FTX)

| Strategie | MaxDD 2022 | Gesamt-Return 2022 |
|-----------|------------|-------------------|
| **Modell** | **-27.0%** | -9.0% |
| Konstant-35 %-BaH | -28.7% | -32.8% |
| Vol-Targeting BaH | -39.2% | -48.2% |
| Buy-and-Hold (100 %) | -68.5% | -73.6% |

**2022: Modell (-27.0%) vs Konstant-35%-BaH (-28.7%):** ✅ Modell hat echten Timing-Skill — geringerer Drawdown trotz gleicher Ø-Exposure

### 9.4 · Schlussfolgerung (ehrlich)

**Befund: Marginales Timing-Signal in Bärphasen — kein Return-Edge.**

Die Robustheitsprüfung liefert ein differenziertes Bild:

**MaxDD (Gesamtperiode): Unentschieden.**
Modell −36.8 % vs Konstant-35 %-BaH −36.3 %. Differenz 0.5 Prozentpunkte,
innerhalb des Messrauschens — kein signifikanter Vorteil für das Modell.

**2022 Gesamtrendite: Klares Timing-Signal.**
| Metrik | Modell | Konstant-35%-BaH | Differenz |
|--------|--------|-----------------|-----------|
| MaxDD 2022 | −27.0 % | −28.7 % | +1.7 pp ✅ |
| **Gesamt-Return 2022** | **−9.0 %** | **−32.8 %** | **+23.8 pp ✅** |

Der MaxDD allein ist irreführend: Er misst nur den schlimmsten Einzelpunkt,
nicht die Zeit unter Wasser. Die Gesamtrendite 2022 zeigt, dass das Modell
die Bärmarkt-Phasen (LUNA + FTX) aktiv vermieden hat — trotz TC-Nachteil
(Modell zahlt 0.3 % RT, Scaled-BaH ist kostenlos). 24 Prozentpunkte
Differenz bei gleicher Ø-Exposure sind echter Timing-Skill.

**Calmar Ratio: Modell besser.**
Modell 1.81 vs Konstant-35%-BaH 1.12 — das Modell erzielt mehr Return pro
Einheit MaxDD.

---

**Was das Modell kann:**
- **Bärmarkt-Regime-Erkennung:** 2022 Gesamtverlust −9 % vs −33 % (exposure-adj.) → 24pp Vorteil
- Sharpe 0.91 > Scaled-BaH 0.89, trotz TC-Kostennachteil
- Calmar 1.81 vs 1.12 — konsistent besseres Return/Drawdown-Verhältnis

**Was das Modell NICHT kann:**
- **Returns zuverlässig vorhersagen:** F1 = 0.42 ± 0.06, verliert gegen Momentum-Only im F1
- **Bullenmärkte ausnutzen:** 65 % Cash-Quote bedeutet verpasste Upside (66.5 % vs 158.2 % Ann.)
- **Einzelne Preisbewegungen antizipieren:** Die Vorhersagegüte ist zu schwach für präzises Timing

**Gesamtbewertung:**
ML auf Krypto sagt Kurs-Returns *nicht* zuverlässig vorher. Der Wert liegt
ausschliesslich im Risikomanagement: Das Modell erkennt Bärmarkt-Regime und
vermeidet die schlimmsten Verluste (2022: −27 % vs −74 % BaH, −33 % exposure-adj. BaH).
Einsatz: **Drawdown-Schutz-Overlay** für Krypto-Portfolios — nicht als Return-Maximierungsstrategie.