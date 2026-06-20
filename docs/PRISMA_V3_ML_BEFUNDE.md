# PRISMA V3 — ML-Befunde & Testdokumentation

**Stand:** 2026-06-20
**Zweck:** Wissenschaftlicher Nachweis aller ML-Experimente — Methodik, Durchläufe, Ergebnisse, Schlussfolgerungen.
**Verwendung:** Arbeitsdokument + Grundlage für das Begleitdokument an den Dozenten (FHNW BI Modul).

> Dieses Dokument hält fest, **wie** getestet wurde und **was** dabei herauskam — ehrlich, inkl. Negativbefunde.
> Methodische Strenge (Purged CV, Baselines, Netto-Kosten, exposure-gematchte Vergleiche) ist hier der eigentliche Wert.

---

## 1 · Methodik (für alle Durchläufe gültig)

**Datenbasis (point-in-time):** Alle Features ausschließlich aus der DB (`stock_price_history`, `crypto_price_history`, `macro_rates`) — kein Live-yfinance im Trainingspfad, kein Look-Ahead. Fundamentals bewusst **nicht** im ML (keine gratis PIT-korrekten CH-Fundamentals verfügbar; sie speisen den Quant-Scorer, siehe v33 TEIL F).

**Validierung:** Purged & Embargoed Walk-Forward Cross-Validation. Embargo = Vorhersagehorizont (verhindert Leakage durch überlappende Forward-Fenster). Mehrere rollende Folds, Streuung ausgewiesen.

**Baselines (Pflicht — ein Modell ist nur so gut, wie es die naive Alternative schlägt):**
- Mehrheitsklasse / konstantes Quantil
- Momentum-only
- Buy-and-Hold (Krypto) bzw. Quant-only (Aktien)
- Exposure-gematchte Baseline (konstante Investitionsquote) — isoliert echten Timing-Skill von reiner Unter-Investition

**Kosten:** Netto-Betrachtung nach Transaktionskosten (Krypto 0.3% round-trip angenommen).

**Bewertung:** Klassifikation → Macro-F1 / Accuracy. Regression → Pinball-Loss je Quantil / MAE. Strategie → Sharpe, Max-Drawdown, Calmar, Netto-Return.

---

## 2 · Durchlauf 1 — Aktien, Quantil-Regression (30d Excess vs SMI)

**Setup:** 30 SMI/SMIM-Titel, monatliche Snapshots 2015–2026, N=3654. Target = 30-Handelstage-Excess-Return vs SMI. LightGBM Quantil (q10/q50/q90). 5-Fold Purged CV.

**Ergebnis (Pinball-Loss, niedriger = besser):**

| Quantil | Modell | Baseline (konstant) | Δ |
|---|---|---|---|
| q10 | 0.01782 ± 0.00172 | 0.01532 | +0.00250 (schlechter) |
| q50 | 0.03180 ± 0.00214 | 0.03069 | +0.00111 (schlechter) |
| q90 | 0.01585 ± 0.00067 | 0.01514 | +0.00071 (schlechter) |

Top-Features: return_3m, momentum_vs_smi_3m, vol_30d.

**Schlussfolgerung:** **Kein Edge.** Das Modell schlägt eine konstante Quantil-Baseline nicht. Erwartbar: 30-Tage-Excess-Returns von liquiden Schweizer Large-Caps sind extrem signalarm, und die effektive Stichprobe ist durch Fensterüberlappung klein. Pipeline korrekt, Signal schwach.

---

## 3 · Durchlauf 2 — Krypto v1 (7d, wöchentlich)

**Setup:** 6 Coins (BTC/ETH/SOL/ADA/BNB/XRP), wöchentliche Snapshots 2017–2026, N=2430. Fear&Greed historisch. Zwei Targets.

**Target (a) — Direktional, H=7d (>+2% = UP):**

| Metrik | Modell | Mehrheitsklasse | Momentum-only |
|---|---|---|---|
| F1 | 0.393 ± 0.075 | 0.000 | 0.457 ± 0.079 |
| Accuracy | 0.547 | — | — |

Netto-Return-Simulation: Modell +0.40% vs Buy-and-Hold +1.18% (7d Ø).

**Target (b) — Excess-Return vs BTC (Altcoins):**

| Metrik | Modell | 0-Baseline |
|---|---|---|
| MAE | 0.073 ± 0.016 | 0.058 ± 0.017 |
| DirAcc | 0.520 | 0.452 |

**Schlussfolgerung:** Schlägt Mehrheitsklasse, **verliert aber gegen Momentum-only und gegen Buy-and-Hold** (Bullmarkt-Drift dominiert, 35% Signalrate → 65% in Cash). Target (b) schlechter als Nullbaseline (Übergeneralisierung). Kein verwertbarer Return-Edge.

---

## 4 · Durchlauf 3 — Krypto v2 (30d, täglich, risikoadjustiert)

**Setup:** 6 Coins, **tägliche** Snapshots 2017–2026, N=16.686 (14.720 OOS), H=30d, Embargo=30d. **MVRV** via Coin Metrics Community API (BTC+ETH, 3457 Tage, kostenlos). Bewertung risikoadjustiert + monatliches überlappungsfreies Rebalancing.

**Risikoadjustiert (OOS, netto 0.3% RT):**

| Strategie | Sharpe | Ann. Return | Max-Drawdown | Calmar |
|---|---|---|---|---|
| Modell (Long wenn p≥0.5) | 0.91 | 66.5% | −36.8% | 1.81 |
| Konstant-35%-BaH (exposure-matched) | 0.89 | 40.7% | −36.3% | 1.12 |
| Vol-Targeting BaH | 0.80 | 64.2% | −53.1% | 1.21 |
| Buy-and-Hold (100%) | 0.89 | 158.2% | −77.5% | 2.04 |

**Bärmarkt 2022 (LUNA/FTX):**

| Strategie | MaxDD 2022 | Return 2022 |
|---|---|---|
| Modell | −27.0% | −9.0% |
| Konstant-35%-BaH | −28.7% | −32.8% |
| Vol-Targeting | −39.2% | −48.2% |
| Buy-and-Hold | −68.5% | −73.6% |

**Edge-Stabilität (F1 je Fold):** 0.479 / 0.436 / 0.477 / 0.319 / 0.397 → Ø 0.422 ± 0.059. Schlägt Mehrheitsklasse in 4/5 Folds; Momentum gewinnt im Gesamt-F1.

**Feature-Importance:** vol_30d, return_90d, excess_vs_btc_30d, **mvrv (Rang 4)**, drawdown_90d.

**Schlussfolgerung:**
- **Kein Return-Prädiktor:** Über die Gesamtperiode gleichauf mit der exposure-gematchten Baseline (Sharpe 0.91 vs 0.89, MaxDD −36.8% vs −36.3%). Pauschal kein Edge.
- **Aber echter Regime-/Risiko-Edge:** Calmar 1.81 vs 1.12 (exposure-matched, robust über ganze OOS-Periode) und 2022 −9% vs −32.8% (exposure-matched). Das Modell ging *gezielt* in der Bärphase raus — nicht bloß generell weniger investiert. Das ist Timing-Skill, kein Konstruktionsartefakt.
- **Ehrliche Einordnung:** Calmar ist die robuste Mehrperioden-Evidenz; 2022 ist die illustrative Fallstudie (n=1 Bärmarkt — nicht überbewerten).

---

## 5 · Gesamtbefund

1. **ML sagt Returns nicht zuverlässig vorher** — weder Aktien noch Krypto, bei sauberer Purged-CV gegen ehrliche Baselines. Das ist ein normales, in der Quant-Praxis häufiges Ergebnis und kein Pipeline-Fehler.
2. **ML liefert messbares Regime-/Risiko-Timing** bei Krypto (Drawdown-Reduktion, Calmar-Vorteil, Bärmarkt-Vermeidung 2022).
3. **Momentum trägt Signal** (schlägt das ML im direktionalen F1) — der simple Trend-Anteil ist nicht wegzudenken.
4. **Der eigentliche Produkt-Test steht noch aus:** Die v33-Vision („historisch validierte Win-Rate") misst das **kombinierte** Signal (quant + ml + macro) über `signal_outcomes` + Backtest — das ist Phase 3 und wurde noch nicht gemessen. Aus dem isolierten ML-Befund darf **nicht** auf das Gesamtprodukt geschlossen werden.

## 6 · Implikationen für die nächsten Schritte

- **ml_score bekommt eine ehrliche Rolle:** bei Krypto Risiko-/Regime-Filter (Exposure drosseln in Gefahrphasen), bei Aktien gering gewichtet.
- **Phase 3 ist der echte Test:** Signal-Aggregation + `signal_outcomes` + Backtest → erst dort entscheidet sich, ob PRISMA eine validierte Win-Rate hat.
- **Verbesserungshebel** (detailliert in v33 TEIL G): News-RAG-Features (C5), Cross-Sectional Ranking bei Aktien (C2), Momentum+ML-Ensemble, visuelle Chart-Analyse für Explainability.

---

*PRISMA V3 ML-Befunde · 2026-06-20 · Andrea Petretta · FHNW BI Modul FS 2026*
