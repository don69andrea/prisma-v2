# PRISMA V3 — ML-Befunde & Testdokumentation

**Stand:** 2026-06-21
**Zweck:** Wissenschaftlicher Nachweis aller ML-Experimente — Methodik, Durchläufe, Ergebnisse, Schlussfolgerungen.
**Verwendung:** Arbeitsdokument + Grundlage für das Begleitdokument an den Dozenten (FHNW BI Modul).

> Dieses Dokument hält fest, **wie** getestet wurde und **was** dabei herauskam — ehrlich, inkl. Negativbefunde.
> Methodische Strenge (Purged CV, strikter Walk-Forward, Baselines, Netto-Kosten, exposure-gematchte
> Vergleiche) ist hier der eigentliche Wert. Kernlehre dieses Dokuments: **In-Sample-Optimismus ist real
> und gefährlich — erst strikter Walk-Forward zeigt die Wahrheit.**

---

## 1 · Methodik (für alle Durchläufe gültig)

**Datenbasis (point-in-time):** Alle Features ausschließlich aus der DB (`stock_price_history`, `crypto_price_history`, `macro_rates`) — kein Live-yfinance im Trainingspfad, kein Look-Ahead. Fundamentals bewusst **nicht** im ML (keine gratis PIT-korrekten CH-Fundamentals; sie speisen den Quant-Scorer, siehe v33 TEIL F).

**Validierung:** Purged & Embargoed Cross-Validation und — entscheidend — **strikter Walk-Forward (Expanding Window)** für die finale Aussage. Embargo = Vorhersagehorizont.

**Baselines (Pflicht):** Mehrheitsklasse / konstantes Quantil; Momentum-only; Buy-and-Hold; **Exposure-gematchte Baseline** (konstante Investitionsquote) — isoliert echten Timing-Skill von reiner Unter-Investition.

**Kosten:** Netto nach Transaktionskosten (CH-Aktien ~0.9% RT, Krypto ~0.5% RT).

**Bewertung:** Klassifikation → Macro-F1/Accuracy. Regression → Pinball/MAE. Strategie → Sharpe, Max-Drawdown, Calmar, Netto-Return.

---

## 2 · Durchlauf 1 — Aktien, Quantil-Regression (30d Excess vs SMI)

**Setup:** 30 SMI/SMIM-Titel, monatliche Snapshots 2015–2026, N=3654. 5-Fold Purged CV. LightGBM Quantil.

| Quantil | Modell (Pinball) | Baseline (konstant) | Δ |
|---|---|---|---|
| q10 | 0.01782 ± 0.00172 | 0.01532 | +0.00250 (schlechter) |
| q50 | 0.03180 ± 0.00214 | 0.03069 | +0.00111 (schlechter) |
| q90 | 0.01585 ± 0.00067 | 0.01514 | +0.00071 (schlechter) |

**Schlussfolgerung:** **Kein Edge.** Schlägt die konstante Quantil-Baseline nicht. 30-Tage-Excess-Returns liquider CH-Large-Caps sind extrem signalarm.

---

## 3 · Durchlauf 2 — Krypto v1 (7d, wöchentlich)

**Setup:** 6 Coins, wöchentlich 2017–2026, N=2430.

Target (a) direktional 7d: F1 0.393 (Modell) vs 0.000 (Mehrheit) vs **0.457 (Momentum)**; Accuracy 0.547. Netto-Return Modell +0.40% vs Buy-and-Hold +1.18%.
Target (b) Excess vs BTC: MAE 0.073 (Modell) vs **0.058 (Nullbaseline)**; DirAcc 0.520 vs 0.452.

**Schlussfolgerung:** Schlägt Mehrheitsklasse, **verliert gegen Momentum und Buy-and-Hold**. Kein verwertbarer Edge.

---

## 4 · Durchlauf 3 — Krypto v2 (30d, täglich) — ⚠️ Ergebnis war IN-SAMPLE-OPTIMISTISCH

**Setup:** 6 Coins, täglich 2017–2026, N=16.686, H=30d, Embargo=30d. MVRV via Coin Metrics. 5-Fold Purged CV, risikoadjustierte Bewertung.

**Damaliges Ergebnis (Purged CV):** Modell Sharpe 0.91 / Calmar **1.81** / MaxDD −36.8% gegen Exposure-Matched Calmar 1.12. 2022: −9% vs −33%. Sah nach echtem Regime-/Drawdown-Edge aus.

> ⚠️ **Dieser Befund hat dem strikten Walk-Forward-Test (Durchlauf 4) NICHT standgehalten.** Ursache:
> Die 5 Purged-CV-Folds hatten über Expanding-Window Zugang zu 2022-Crash-Daten in *anderen* Folds;
> das finale Modell „kannte" Crash-Merkmale, die es im echten OOS nicht gekannt hätte. Der Calmar 1.81
> ist **In-Sample-Optimismus**, keine OOS-Performance. Maßgeblich ist Durchlauf 4.

---

## 5 · Durchlauf 4 — Krypto, strikter Walk-Forward (KERN-VALIDIERUNG)

**Setup:** 6 Coins, täglich, OOS, ML als Exposure-/Risiko-Overlay. **Strikter Expanding-Window Walk-Forward** (jeder Fold sieht nur Vergangenheit), Schwelle a priori, Vergleich gegen Exposure-Matched-Baseline (Timing-Skill-Test).

**Kern-Tabelle:**

| Metrik | ML-Timing | Exposure-Matched | Buy-and-Hold |
|---|---|---|---|
| ∅ Investitionsquote | 28% | 28% | 100% |
| CAGR | +23.2% | +20.1% | +55.1% |
| Sharpe | 0.77 | 0.93 | 0.93 |
| Max-Drawdown | −65.9% | −30.5% | −77.3% |
| Calmar | 0.35 | 0.66 | 0.71 |

**Fold-Analyse:**

| Zeitraum | ML Calmar | EM Calmar | ∅ Exposure | Interpretation |
|---|---|---|---|---|
| 2019–20 | 0.11 | 1.16 | 9.1% | Modell fast nie IN, IN-Tage treffen Crash-Tage (Anti-Momentum) |
| 2021–22 | −0.16 | 0.92 | 31.6% | Auf 2020-Bull trainiert → zu bullish → bleibt IN im 2022-Crash |
| 2023–24 | 5.78 | 2.22 | 40.7% | Echter Timing-Skill (ML > EM) — aber einzelfold-isoliert |
| 2025–26 | 0.17 | −0.44 | 31.8% | ML > EM, kleines Fenster |

**Schlussfolgerung:** **Kein robuster, generalisierbarer Timing-Skill.** ML-Calmar (0.35) liegt **unter** der Exposure-Matched-Baseline (0.66) — der scheinbare Vorteil kommt aus geringerer Investitionsquote, nicht aus Timing, und ist nicht einmal effizient. Echter Skill nur in **einem** Fold (2023–24, klare Post-Crash-Recovery). In normalen Bullmärkten und Erholungsphasen nach Bär-Training versagt das Modell strukturell (Anti-Momentum-Eintritt).

---

## 6 · Gesamtbefund (final)

1. **Kein robuster ML-Edge** — weder Return-Vorhersage (Aktien/Krypto) noch generalisierbares Regime-Timing, bei strikt sauberer Methodik. Mehrfach, an verschiedenen Granularitäten getestet.
2. **In-Sample-Optimismus ist die zentrale Lehre:** Purged CV (Calmar 1.81) → strikter Walk-Forward (Calmar 0.35). Die Lücke ist der eigentliche wissenschaftliche Befund — und genau der Fehler, den naive „wir schlagen den Markt"-Projekte machen.
3. **Quant + Macro allein** schlagen Buy-and-Hold ebenfalls nicht (Aktien Sharpe −0.35 vs 0.43; Krypto-Floor Sharpe 0.06).
4. **Momentum trägt das meiste Signal** — der simple Trend-Anteil schlägt das ML im direktionalen F1.
5. **Statistische Power:** N oft zu klein für harte Aussagen (Monats-Backtest N=25, CI ±20pp) — daher „kein nachweisbarer Edge", nicht „bewiesen kein Edge". Bei Krypto-WF (Durchlauf 4) ist der Negativbefund jedoch robust über alle Folds bis auf einen.

## 7 · Implikationen für das Produkt & nächste Schritte

- **ml_score-Rolle:** in der Produktion **aus/minimal**. Das ML bleibt als **dokumentierte Forschungskomponente** (saubere Pipeline + ehrliche Negativ-Evaluation) — das erfüllt die „ML-basiert"-Vorgabe voll und demonstriert Methodik-Kompetenz.
- **Produktwert liegt woanders:** angereicherte Multi-Source-Datensicht, Agentic-Analyse, RAG, fundamentaler Quant-Score als Decision-Support, und **visuelle Chart-Analyse für Erklärbarkeit** (v33 TEIL G4).
- **Einziger ungetesteter Informationshebel:** News-RAG-Features (C5) — wirklich neue Information jenseits von Preis/Technik. Optional, nicht projektkritisch.
- **Nächster Schritt:** Dashboard (v33 TEIL G/Kap. 8) — macht die vorhandene Arbeit sichtbar und benotbar.

---

*PRISMA V3 ML-Befunde · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
