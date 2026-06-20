# ML Evaluation — Quantil-Regression (TEIL F §F2/§F3)

**Trainiert:** 2026-06-20  
**Modell:** LightGBM `objective=quantile`, 3 Quantile (q10/q50/q90)  
**Feature-Hash:** `b9248440`  
**N Samples:** 3,654  
**N Tickers:** 30  
**Zeitraum:** 2016-02-01 → 2026-05-01  
**CV:** Purged & Embargoed Walk-Forward, 5 Folds, Embargo=30 Handelstage  

---

## Pinball-Loss (CV, Mittel ± Std über Folds)

| Quantil | Modell | Baseline (konst.) | Δ (Modell − Baseline) | Modell schlägt Baseline? |
|---------|--------|-------------------|----------------------|--------------------------|
| q10 | 0.01782 ± 0.00172 | 0.01532 | +0.00250 | ❌ |
| q50 | 0.03180 ± 0.00214 | 0.03069 | +0.00111 | ❌ |
| q90 | 0.01585 ± 0.00067 | 0.01514 | +0.00071 | ❌ |

**Alle 3 Quantile besser als Baseline:** ❌ NEIN — Review nötig

---

## Feature-Importances (q50-Modell, Gain)

| Rang | Feature | Importance |
|------|---------|-----------|
| 1 | `return_3m` | 748.0 |
| 2 | `momentum_vs_smi_3m` | 731.0 |
| 3 | `vol_30d` | 722.0 |
| 4 | `vol_90d` | 712.0 |
| 5 | `drawdown_12m` | 709.0 |
| 6 | `rsi_14` | 693.0 |
| 7 | `return_12m` | 689.0 |
| 8 | `macd_hist` | 684.0 |
| 9 | `return_6m` | 678.0 |
| 10 | `bb_position` | 675.0 |
| 11 | `return_1m` | 670.0 |
| 12 | `price_to_52w_high` | 619.0 |
| 13 | `inflation_ch` | 250.0 |
| 14 | `snb_rate` | 220.0 |
| 15 | `chf_eur` | 200.0 |

---

## Feature-Set (TEIL F §F2)

Preis/Technik (aus `stock_price_history`): `return_1m`, `return_3m`, `return_6m`, `return_12m`, `vol_30d`, `vol_90d`, `rsi_14`, `price_to_52w_high`, `momentum_vs_smi_3m`, `bb_position`, `macd_hist`, `drawdown_12m`

Makro (aus `macro_rates`): `snb_rate`, `chf_eur`, `inflation_ch`

**Keine Fundamental-Features** (TEIL F §F2 — CH-Fundamentalhistorie nicht PIT-verfügbar)


---

## Validierungs-Methodologie

- **Purged & Embargoed Walk-Forward CV** (López de Prado, Kap. 16)

- Embargo = 30 Handelstage zwischen Train- und Test-Block

- Überlappende 30d-Targets sind dokumentiert; CV-Purging verhindert Leakage

- Monotonie-Fix: q10 ≤ q50 ≤ q90 nach Element-weisem Sort erzwungen

- `prob_outperform`: lineare CDF-Interpolation aus (q10, q50, q90) — dokumentierte Approximation


---

## Baselines

- **Majority-Class / Constant-Q**: Konstantes Quantil = Trainings-Quantil der Zielgrösse

- Weitere Baselines (Momentum-only, Quant-only) können via `--baselines extended` aktiviert werden
