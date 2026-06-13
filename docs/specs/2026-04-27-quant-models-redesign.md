# Quant-Models Redesign — Diversification & Quality AI ersetzen

**Status: Draft — 2026-04-27**
**Autor: Fabia Holzer / Claude Code**
**Bezieht sich auf**: `docs/specs/2026-04-21-prisma-v2-design.md` (§6, §7, §8.1, §13), `docs/specs/2026-04-28-narrative-engine.md` (§5.2, §10.2), `docs/specs/2026-04-28-mcp-server.md` (§4.1, §4.3)

---

## 1. Problem

Die ursprüngliche Modell-Liste der Design-Spec v1.1 (5 Modelle) enthält zwei Modelle, die mit den verfügbaren Datenquellen (Yahoo Finance gratis + FinancialModelingPrep Free Tier) **nicht oder nur mit hohem Bias-Risiko** umsetzbar sind:

| Modell | Problem |
|---|---|
| **Quality AI** (Lasso-Regression mit rollendem 2J-Fenster + Forward-Returns) | Braucht **point-in-time** Fundamentaldaten zum jeweiligen historischen Stichtag (as-reported, ohne nachträgliche Restatements). FMP Free liefert nur aktuelle Snapshots; FMP Starter liefert Historicals **ohne explizites Restatement-Flag** → Look-Ahead-Bias unvermeidbar. Saubere PIT-Quellen (Bloomberg, SIX) sind nicht im Projektbudget. |
| **Anti-Cyclical** (P/E + P/B unter 3J-Median) | Braucht historische P/E-Reihen über 3 Jahre. FMP Free liefert kein Historical, Yahoo liefert für CH-Tickers (.SW) keine zuverlässigen historischen Ratios. |

Zusätzlich wurde ursprünglich auch **Diversification** als Tausch-Kandidat diskutiert. Diese bleibt aber drin, weil sie nur Tagespreise braucht (Yahoo, gratis).

## 2. Entscheidung

**Zwei Modelle raus, zwei rein, ein Modell zusätzlich gestrichen** — neue Liste hat 5 Modelle (statt vorher 5):

| # | Modell | Kategorie | Status | Datenquelle |
|---|---|---|---|---|
| 1 | Quality Classic | Quality | bleibt | Yahoo + FMP Free |
| 2 | Alpha | Trend | bleibt | Yahoo only |
| 3 | **Trend Momentum** | Trend | **NEU** | Yahoo only |
| 4 | **Value Alpha Potential** | Value | **NEU** | Yahoo only |
| 5 | Diversification | Risk | bleibt | Yahoo only |

**Raus**: Quality AI (PIT-Daten unbezahlbar), Anti-Cyclical (Historicals fehlen).

**Kategorie-Verteilung neu**: Quality ×1, Trend ×2, Value ×1, Risk ×1 — keine Pillar fällt komplett weg, Trend ist neu doppelt vertreten (Alpha = absolut/Sharpe-gewichtet, Trend Momentum = relativ/EWMA).

## 3. Modell-Specs

### 3.1 Trend Momentum (Kategorie: Trend) — NEU

**Idee**: Welche Aktien haben in jüngster Zeit konsistent stärker performt als der Markt? Frischer Schwung zählt mehr als alter.

**Inputs**:
- `prices: pd.DataFrame` — Tagespreise aller Tickers im Universum (Yahoo, ~2 Jahre Historie für stabile EWMA)
- Benchmark: **Equal-Weighted-Mittel** des Universums, `prices.mean(axis=1)` — bewusst gegen cap-gewichtetes ^SSMI, das von Nestlé/Roche dominiert würde

**Berechnung** (3 Schritte):

```python
# Schritt 1: Tägliche relative Returns vs. Equal-Weighted-Benchmark
stock_returns = prices.pct_change()
benchmark_returns = prices.mean(axis=1).pct_change()
rel_returns = stock_returns.sub(benchmark_returns, axis=0)

# Schritt 2: EWMA mit halflife = 63 Tage (~3 Monate)
exp_momentum = rel_returns.ewm(halflife=63, min_periods=32).mean()

# Schritt 3: Snapshot der letzten Zeile + Ranking
score = exp_momentum.iloc[-1]
rank = score.rank(ascending=False, method="min").astype(int)
```

**Begründung halflife=63**: Heute = volles Gewicht, vor 63d = 50%, vor 126d = 25%, vor 252d = 12.5%. Filtert kurzfristiges Rauschen, behält 3–12-Monats-Trend (klassisches Momentum-Window à la Jegadeesh-Titman 1993, Carhart 1997).

**Output**: `list[ModelRankingResult]` mit `ticker`, `score`, `rank` (1 = stärkstes Momentum).

**Edge-Cases**:
- < 32 Datenpunkte: `min_periods=32` liefert NaN → Ticker wird mit `rank=None` und `confidence="low"` markiert
- Ticker fehlt komplett aus Universum-Preistabelle: Fehler aus Daten-Sync-Stage, nicht aus Modell

**Was es NICHT tut**:
- Kein Volatility-Adjustment (im Gegensatz zu Alpha, das Sharpe einbaut)
- Keine Sektor-Neutralisierung
- Keine Timing-Filter

---

### 3.2 Value Alpha Potential (Kategorie: Value) — NEU

**Idee**: Welche Aktien stehen aktuell deutlich unter ihrem persönlichen Outperformance-Hoch? Mean-Reversion-Annahme: starke Outperformer kehren zu ihrem Peak zurück.

**Inputs**:
- `prices: pd.DataFrame` — Tagespreise (Yahoo, ~1.5 Jahre Historie für 252d-Rolling-Window)
- Benchmark: identisch zu Trend Momentum (Equal-Weighted-Universe)

**Berechnung** (4 Schritte):

```python
# Schritt 1: Rolling 63-Tage-Alpha (3M Stock-Return − 3M Benchmark-Return)
horizon = 63
stock_3m_ret = prices.pct_change(horizon)
benchmark_3m_ret = prices.mean(axis=1).pct_change(horizon)
alpha = stock_3m_ret.sub(benchmark_3m_ret, axis=0)  # Zeitreihe pro Ticker

# Schritt 2: Rolling Maximum über 252 Tage (1 Jahr)
rolling_max_alpha = alpha.rolling(window=252, min_periods=68).max()

# Schritt 3: Distance to Peak
potential = rolling_max_alpha - alpha

# Schritt 4: Snapshot + Ranking
score = potential.iloc[-1]
rank = score.rank(ascending=False, method="min").astype(int)
```

**Begründung Window-Wahl**:
- Alpha-Horizont **63d (3M)**: dokumentierte Spec-Lücke aus dem `Stock_Selection.txt`-Original (Spec spezifiziert keinen Horizont). Wahl 63d = konsistent mit Trend Momentum, klassisches 3M-Performance-Window.
- Rolling-Max-Window **252d (1J)**: lang genug für echte Peaks, kurz genug um nicht zu stale zu werden.

**Output**: `list[ModelRankingResult]` (1 = grösstes Snap-Back-Potenzial).

**Edge-Cases**:
- < 68 Datenpunkte (`min_periods` für rolling max): Ticker bekommt `rank=None`
- Negativer `potential` ist möglich (aktuelles Alpha über Rolling-Max, weil neuer Peak heute) → Score wird trotzdem geranked, nur Distance ist negativ

**Was es NICHT tut**:
- Kein Fundamental-Check ("ist der Drop gerechtfertigt?")
- Keine Volatility-Adjustment
- Kein Quality-Gate (kann Junk-Stocks ranken die zu Recht gefallen sind) → Master-Rank-Aggregation balanciert das durch andere Pillars

---

### 3.3 Quality Classic (unverändert)

Bleibt wie in §6.1 der Design-Spec. Datenstrategie: Yahoo first, FMP Free als Fallback für CH-Tickers wo Yahoo lückenhaft ist. Kein Code-Change im Modell, nur in der Daten-Adapter-Schicht.

### 3.4 Alpha (unverändert)

Bleibt wie in §6.3. Yahoo only.

### 3.5 Diversification (unverändert)

Bleibt wie in §6.5. Yahoo only.

---

## 4. Aggregation (Update §7)

### 4.1 Standard-Aggregation
```
TotalRank = Ø(QualityClassic, Alpha, TrendMomentum, ValueAlphaPotential, Diversification)
```

### 4.2 Default-Gewichte (gleichgewichtet, je 0.20)
```json
{
  "quality_classic": 0.20,
  "alpha": 0.20,
  "trend_momentum": 0.20,
  "value_alpha_potential": 0.20,
  "diversification": 0.20
}
```

### 4.3 Sweet Spot
Bleibt: ≥3 von 5 Modellen Top-25%. Da die Pillars sich verschoben haben (Trend doppelt), wird ein Sweet-Spot-Stock typischerweise gleichzeitig Trend-stark und auf einer der anderen Achsen stark — bewusst akzeptiert.

### 4.4 Widerspruchs-Erkennung (Update §8.1)
Alte Regel ("Quality top, Diversification bottom") bleibt. Neue Regel hinzu:
> Wenn **Trend Momentum** Top-20% **und** **Value Alpha Potential** Top-20% gleichzeitig → Contradiction "Stock outperformt aktuell stark, ist aber gleichzeitig weit unter seinem Alpha-Peak". Selten, aber interpretationsbedürftig.

---

## 5. Datenquellen-Update (§13)

| Quelle | Nutzung neu |
|---|---|
| yfinance | Tagespreise (Models 2–5), Fundamentals-Snapshot (Model 1 primär) |
| FinancialModelingPrep Free Tier | Fundamentals-Backup für Quality Classic bei CH-Tickers; **250 Calls/Tag**; **kein Historical** verfügbar |
| Finnhub Free Tier | News/Earnings-Dates für Layer-2 Sentiment-Agent (unverändert) |

**Env-Migration**: `.env` enthält bisher `FINNHUB_API_KEY` für FMP-Key (historisch). Wird umbenannt zu `FMP_API_KEY`. Finnhub-Key separat ergänzen, falls Layer-2-Sentiment aktiv wird.

## 6. Skeleton-Code-Layout

```
backend/
  domain/
    models/
      __init__.py
      base.py                       # BaseModel-Protocol, ModelRankingResult VO
      quality_classic.py            # Stub mit run() raise NotImplementedError
      alpha.py                      # Stub
      trend_momentum.py             # Stub
      value_alpha_potential.py      # Stub
      diversification.py            # Stub
backend/tests/unit/models/
  test_quality_classic.py           # Skeleton — golden_dataset fixture TODO
  test_alpha.py                     # Skeleton
  test_trend_momentum.py            # Skeleton — formula assertions TODO
  test_value_alpha_potential.py     # Skeleton
  test_diversification.py           # Skeleton
```

Alle Stubs implementieren das `BaseModel`-Protocol mit `run(universe_data: UniverseData) -> list[ModelRankingResult]`, werfen aber `NotImplementedError`. Tests sind als `pytest.mark.skip(reason="implementation pending")` markiert mit dokumentiertem Expected-Behavior.

## 7. Migration-Schritte (Doku-Sweep)

| Datei | Änderung |
|---|---|
| `docs/specs/2026-04-21-prisma-v2-design.md` | §6.2 ersetzen durch Trend Momentum, §6.4 (Anti-Cyclical) entfernen, §6.5 bleibt, neue §6.X für Value Alpha Potential. §7.1/§7.2 Default-Weights aktualisieren. §8.1 neue Widerspruchs-Regel ergänzen. §13 Datenquellen-Hinweis (FMP Free, kein Historical). §18 Risiko "Lasso instabil" entfernen. §19 Stretch-Goals: "Relative Momentum (EWMA)" und "Alpha Potential" entfernen (jetzt in MVP). |
| `docs/specs/2026-04-28-narrative-engine.md` | §5.2 User-Prompt Template: Quality AI → Trend Momentum, Anti-Cyclical → Value Alpha Potential. §10.2 Fixture-Filenames anpassen. |
| `docs/specs/2026-04-28-mcp-server.md` | §4.1 Default-Weights-Beispiel, §4.3 dimensions-Beispielliste. |
| `README.md` | Z.11 Modell-Liste. |
| `frontend/app/page.tsx` | Z.19 Beschreibung. |
| `.env` | `FINNHUB_API_KEY` → `FMP_API_KEY` (Wert bleibt). |

## 8. Test-Strategie

Pro neues Modell:
1. **Golden-Dataset** in `backend/tests/fixtures/quant/`: synthetische Preistabelle (z.B. 20 Tickers × 500 Tage), per Hand vorberechnetes Expected-Ranking.
2. **Unit-Test**: Modell auf Golden-Dataset → assertEqual gegen erwarteten Rang.
3. **Edge-Case-Tests**: zu wenige Daten (NaN-Pfad), nur 1 Ticker (Benchmark = Stock = Alpha 0), konstante Preise (Score 0).
4. **Property-Test** (optional): zufällige Preise → Modell crasht nicht, gibt korrekte Anzahl Ränge zurück.

Coverage-Ziel: ≥90% pro Modell-Modul (sind reine Funktionen, gut testbar).

## 9. Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| EWMA halflife=63 ist Faktor-Choice — Performance auf SMI evtl. enttäuschend | Mittel | Hyperparameter dokumentiert, im Backtest vergleichbar mit halflife=21 / 126 |
| Equal-Weighted-Benchmark divergiert stark von ^SSMI bei Krisen → User verwirrt | Niedrig | UI/Memo dokumentiert: "Benchmark = gleichgewichtetes Universum" |
| Value Alpha Potential ranked Junk-Stocks hoch (zu Recht gefallen) | Mittel | Master-Rank-Aggregation mit Quality Classic + Diversification balanciert das aus |
| FMP Free 250 Calls/Tag bei 20 Tickers + Fundamentals + häufigen Re-Runs schnell aufgebraucht | Mittel | Aggressives Caching im `Factsheet`-Table (TTL 24h Fundamentals) — wie in Original-Spec §13 |
| CH-Ticker-Fundamentals weiterhin lückenhaft trotz FMP-Fallback | Mittel | Quality Classic mit Per-Ticker-`confidence`-Flag; bei <6 von 8 verfügbaren Kennzahlen → `rank=None` für diesen Ticker statt Garbage-Score |

## 10. Open Questions / Out of Scope

- **Value Alpha Potential Horizont = 63d** ist eine Spec-Lücken-Auflösung, kein definierter Wert. Sollte nach erstem Backtest validiert werden — falls Ergebnisse instabil, alternativer Horizont (126d/252d) ausprobieren. Dokumentiert als Backtest-Hyperparameter, nicht als Open Code-Issue.
- **Sektor-Neutralisierung** für Trend Momentum: nicht im MVP, würde Sektor-Ratings verbergen.
- **Multi-Horizon Momentum** (gewichtetes Mittel von halflife 21/63/126): aufgehoben für Stretch-Goals.

## 11. Change Log

| Version | Datum | Autor | Änderung |
|---|---|---|---|
| Draft v1 | 2026-04-27 | Fabia / Claude Code | Initialer Entwurf für Modell-Tausch nach Daten-Feasibility-Check |
