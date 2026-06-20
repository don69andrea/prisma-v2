# ML Evaluation — Krypto (PRISMA V3)

**Trainiert:** 2026-06-20  
**Coins:** BTC, ETH, SOL, ADA, BNB, XRP  
**Horizont:** H=7 Tage  
**Transaktionskosten:** 0.3% Round-Trip  
**CV:** Purged & Embargoed Walk-Forward, 5 Folds, Embargo=14 Tage  
**Up-Rate gesamt:** 40.4% (Anteil 7d-Return > 2%)  
**N Samples (direktional):** 2,430  
**N Samples (Excess-Altcoin):** 1,985  

---

## Target (a): Direktional — 7d-Forward-Return > 2%

### Modell vs Baselines (CV, Mittel ± Std)

| Metrik | Modell | Mehrheitsklasse | Momentum-only |
|--------|--------|-----------------|---------------|
| F1 | 0.393 ± 0.075 | 0.000 ± 0.000 | 0.457 ± 0.079 |
| Accuracy | 0.547 ± 0.023 | — | — |
| Precision | 0.429 ± 0.076 | — | — |
| Recall | 0.369 ± 0.085 | — | — |

**Schlägt Mehrheitsklasse:** ✅ JA  
**Schlägt Momentum-Only:** ❌ NEIN  

### Per-Fold Detail

| Fold | F1 | F1-Majority | F1-Momentum | n_test | up% |
|------|-----|------------|-------------|--------|-----|
| 1 | 0.522 | 0.000 | 0.528 | 359 | 48.5% |
| 2 | 0.430 | 0.000 | 0.524 | 423 | 44.7% |
| 3 | 0.355 | 0.000 | 0.341 | 423 | 33.6% |
| 4 | 0.320 | 0.000 | 0.511 | 423 | 44.9% |
| 5 | 0.336 | 0.000 | 0.384 | 423 | 32.6% |

---

## Netto-Return-Simulation (Signal-Strategie vs Buy-and-Hold)

| Strategie | Ø 7d-Return | Transaktionskosten | Netto |
|-----------|-------------|-------------------|-------|
| Modell (brutto) | 0.508% | 0.3% | 0.403% |
| Buy-and-Hold (alle Coins, avg) | 1.184% | 0% | 1.184% |
| Signal-Rate (Anteil UP-Signale) | 35.0% | — | — |

**Modell (netto) schlägt Buy-and-Hold:** ❌ NEIN  
**Netto-Std über Folds:** 0.503%  

---

## Target (b): Excess-Return vs BTC (Altcoins)

### MAE und Direktions-Accuracy (CV)

| Metrik | Modell | 0-Baseline | Mean-Baseline |
|--------|--------|-----------|----------------|
| MAE | 0.073 ± 0.016 | 0.058 ± 0.017 | 0.059 ± 0.016 |
| DirAcc | 0.520 ± 0.023 | 0.452 ± 0.059 | — |

**MAE schlägt 0-Baseline:** ❌ NEIN  
**MAE schlägt Mean-Baseline:** ❌ NEIN  

### Per-Fold Detail

| Fold | MAE | MAE(0) | MAE(Mean) | DirAcc | DirAcc-BL | n |
|------|-----|--------|-----------|--------|-----------|---|
| 1 | 0.0780 | 0.0597 | 0.0595 | 0.524 | 0.549 | 288 |
| 2 | 0.0961 | 0.0900 | 0.0900 | 0.533 | 0.490 | 353 |
| 3 | 0.0607 | 0.0476 | 0.0500 | 0.554 | 0.418 | 352 |
| 4 | 0.0793 | 0.0537 | 0.0548 | 0.490 | 0.414 | 353 |
| 5 | 0.0507 | 0.0411 | 0.0422 | 0.500 | 0.389 | 352 |

## Feature-Importances (Direktional-Modell, Gain)

| Rang | Feature | Importance |
|------|---------|-----------|
| 1 | `return_30d` | 991.0 |
| 2 | `rsi_14` | 969.0 |
| 3 | `vol_7d` | 948.0 |
| 4 | `drawdown_90d` | 929.0 |
| 5 | `return_7d` | 928.0 |
| 6 | `vol_30d` | 914.0 |
| 7 | `excess_vs_btc_30d` | 913.0 |
| 8 | `return_90d` | 897.0 |
| 9 | `bb_position` | 805.0 |
| 10 | `fear_greed` | 706.0 |
| 11 | `return_1d` | 0.0 |
| 12 | `macd_hist` | 0.0 |

---

## Methodologie

- **Purged & Embargoed Walk-Forward CV** (López de Prado, Kap. 16)
- Embargo = 14 Tage (2× Horizont H=7)
- Features: PIT-korrekt aus `crypto_price_history` (DB) + Fear&Greed (alternative.me)
- Transaktionskosten: 0.15% pro Seite (Taker) + 0.05% Slippage = 0.30% Round-Trip
- Kein MVRV/On-Chain (Glassnode-Key nicht vorhanden)
- Keine 1h-Daten (tägliche Snapshots, wöchentliche Frequenz)

## Bewertung: Welcher Coin/Horizont/Target am besten?

### Up-Rate und mittlerer 7d-Return je Coin

| Coin | N | Up-Rate (>2%) | Ø 7d-Return | Std 7d-Return |
|------|---|--------------|------------|----------------|
| BTC | 445 | 39.3% | 0.87% | 9.05% |
| ETH | 445 | 42.5% | 0.96% | 11.57% |
| SOL | 289 | 44.3% | 1.87% | 13.68% |
| ADA | 410 | 36.8% | 0.42% | 12.25% |
| BNB | 433 | 44.6% | 1.82% | 11.53% |
| XRP | 408 | 35.8% | 0.72% | 13.82% |