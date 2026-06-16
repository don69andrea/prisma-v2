# Spec: Die 5 MVP-Quant-Modelle

**Status: Final**
**Datum: 2026-04-28**
**Autor: Andrea Petretta / Claude Code**
**Bezieht sich auf**: `docs/specs/2026-04-21-prisma-v2-design.md` §6, `docs/specs/2026-04-27-quant-models-redesign.md`

---

## Übersicht

PRISMA verwendet 5 Quant-Modelle, jedes mit einer eigenen Kategorie. Die finale Modell-Liste wurde durch das Redesign-Dokument (2026-04-27) festgelegt:

| # | Modell | Kategorie | Datenquelle | Status |
|---|--------|-----------|-------------|--------|
| 1 | Quality Classic | Quality | Yahoo + FMP Free | ✅ implementiert |
| 2 | Alpha | Trend | Yahoo only | noch offen |
| 3 | Trend Momentum | Trend | Yahoo only | noch offen |
| 4 | Value Alpha Potential | Value | Yahoo only | noch offen |
| 5 | Diversification | Risk | Yahoo only | noch offen |

Alle Modelle implementieren das Interface:

```python
class BaseModel:
    def run(self, ...) -> list[ModelRankingResult]: ...
```

`ModelRankingResult` enthält: `ticker: str`, `score: float | None`, `rank: int | None`, `confidence: Literal["high", "low"]`.

---

## 1. Quality Classic (Kategorie: Quality)

### Business-Problem
Welche Aktien sind fundamental günstig bewertet und finanziell gesund? Kombiniert 8 klassische Kennzahlen zu einem gleichgewichteten Score.

### Formel

```
Input:  fundamentals: dict[ticker, dict[metric, float | None]]

1. Z-Score je Kennzahl über alle Ticker (std == 0 → z = 0)
2. Richtungsanpassung: "niedrig = besser" × (−1)
3. Gleichgewichteter Durchschnitt aller verfügbaren Z-Scores → Quality-Score
4. Rang aufsteigend: höchster Score = Rang 1
```

| Kennzahl | Richtung | yfinance-Field |
|----------|----------|----------------|
| `pe_ratio` | niedrig = besser | `info["trailingPE"]` |
| `pb_ratio` | niedrig = besser | `info["priceToBook"]` |
| `fcf_yield` | hoch = besser | `info["freeCashflow"] / info["marketCap"]` |
| `operating_margin` | hoch = besser | `info["operatingMargins"]` |
| `dividend_yield` | hoch = besser | `info["dividendYield"]` |
| `debt_to_equity` | niedrig = besser | `info["debtToEquity"]` |
| `eps_growth_3y` | hoch = besser | abgeleitet aus `info["earningsGrowth"]` |
| `sales_growth_3y` | hoch = besser | abgeleitet aus `info["revenueGrowth"]` |

### Edge-Cases
- **Einzelne Kennzahl fehlt**: Ticker nimmt an den verbleibenden Kennzahlen teil; kein Z-Score für das fehlende Metric.
- **Alle Kennzahlen fehlen**: `rank=None`, `confidence="low"`.
- **Nur 1 Ticker im Universum**: Std = 0 → Z-Score = 0 für alle → Score = 0 → `rank=1`.
- **Leeres Universum**: Rückgabe `[]`.
- **Std = 0 bei einer Kennzahl** (alle Ticker haben denselben Wert): Z-Score = 0 für alle.

### Test-Approach
- **Golden Dataset**: `_GOOD` (niedrige Ratios, hohe Margen) vs. `_BAD` (umgekehrt) → `_GOOD` muss `rank=1` erhalten.
- **5-Ticker-Dataset**: abgestufte pe_ratio/pb_ratio → strikt monotone Rang-Reihenfolge prüfen.
- **Gleichstand**: 3 identische Ticker → alle `rank=1`.
- **Determinismus**: zweimal ausführen, gleiche Ergebnisse.

### Performance
< 100 ms für ein Universum mit 500 Tickern (pure Python, keine DB).

---

## 2. Alpha (Kategorie: Trend)

### Business-Problem
Welche Aktien haben über mehrere Zeithorizonte konsistent besser performt als ihr Benchmark-Index? Sharpe-gewichtete Outperformance misst nicht nur den Trend, sondern seine Qualität.

### Formel

```
Input:  prices: pd.DataFrame  (index=Datum, columns=Ticker)
        benchmark_prices: pd.Series  (index=Datum, z.B. ^GSPC via yfinance)

Für jeden Horizont h ∈ {5, 63, 126, 252, 504} Handelstage:
    stock_return(h)     = prices.pct_change(h).iloc[-1]
    benchmark_return(h) = benchmark_prices.pct_change(h).iloc[-1]
    outperformance(h)   = stock_return(h) − benchmark_return(h)

Sharpe-Ratio der täglichen Outperformance-Reihe (gesamte Historie):
    daily_excess = prices.pct_change() − benchmark_prices.pct_change()
    sharpe       = daily_excess.mean() / daily_excess.std()  (annualisiert × √252)

Gewichteter Alpha-Score:
    raw_score = Σ(outperformance(h) × weight(h)) + sharpe × sharpe_weight

Gewichte:
```

| Horizont | Handelstage | Gewicht |
|----------|-------------|---------|
| 1 Woche  | 5           | 10%     |
| 3 Monate | 63          | 15%     |
| 6 Monate | 126         | 25%     |
| 1 Jahr   | 252         | 30%     |
| 2 Jahre  | 504         | 20%     |
| Sharpe   | —           | als Qualitätsmass additiv |

```
Z-Score-Normalisierung des raw_score über alle Ticker → Alpha-Score
Rang aufsteigend: höchster Score = Rang 1
```

### Edge-Cases
- **Zu wenig Historie für Horizont h**: `outperformance(h)` wird übersprungen; Gewicht wird auf verfügbare Horizonte umverteilt.
- **Std = 0 bei Sharpe** (Ticker hat 0 tägliche Varianz): Sharpe = 0.
- **Weniger als 32 Handelstage**: Ticker bekommt `rank=None`, `confidence="low"`.
- **Leeres Universum / einzelner Ticker**: analog zu Quality Classic.

### Test-Approach
- **Golden Dataset**: Ticker A hat über alle Horizonte +5% Outperformance, Ticker B −3% → A muss `rank=1`.
- **Gewichtungs-Test**: Kurzer Horizont dominiert wenn lange Daten fehlen.
- **Sharpe-Einfluss**: Ticker mit gleicher Outperformance aber höherer Volatilität → tieferer Score.
- **Deterministisch**: gleiche Preis-DataFrame → gleiche Ränge.

### Performance
< 200 ms für 500 Ticker mit 2 Jahren Tagespreisen (pandas EWMA/pct_change).

---

## 3. Trend Momentum (Kategorie: Trend)

### Business-Problem
Welche Aktien haben zuletzt konsistent stärker performt als der Marktdurchschnitt, mit mehr Gewicht auf jüngeren Daten? Frischt Momentum auf, gewichtet Jüngeres höher als altes.

### Formel

```
Input:  prices: pd.DataFrame  (index=Datum, columns=Ticker, ~2 Jahre Tagespreise)

Benchmark = prices.mean(axis=1)           # Equal-Weighted Universe (kein ^SSMI)

rel_returns = prices.pct_change()
              .sub(benchmark.pct_change(), axis=0)

exp_momentum = rel_returns.ewm(halflife=63, min_periods=32).mean()

score = exp_momentum.iloc[-1]             # letzter EWMA-Wert je Ticker
rank  = score.rank(ascending=False, method="min").astype(int)
```

**halflife=63**: Heute = volles Gewicht, vor 63d = 50%, vor 126d = 25%. Filtert kurzfristiges Rauschen, erfasst 3–12-Monats-Trend (Jegadeesh-Titman 1993, Carhart 1997).

### Edge-Cases
- **< 32 Datenpunkte** (`min_periods=32`): EWMA liefert NaN → `rank=None`, `confidence="low"`.
- **Ticker fehlt in prices-DataFrame**: Fehler in der Daten-Sync-Stage, nicht im Modell — `KeyError` propagieren.
- **Alle Ticker gleich performt**: rel_returns = 0 für alle → alle Score = 0 → alle `rank=1` (Gleichstand).

### Test-Approach
- **Golden Dataset**: Konstruiere prices-DataFrame wo Ticker A in den letzten 63d täglich +0.1% über Benchmark, Ticker B −0.1% → A muss `rank=1`.
- **Gleichstand**: Alle Ticker mit identischen Preisreihen → alle `rank=1`.
- **min_periods**: Ticker mit nur 20 Datenpunkten → `rank=None`.
- **Deterministisch**: gleiche DataFrame → gleiche Ränge.

### Performance
< 100 ms für 500 Ticker × 500 Tage (pandas EWMA ist vektorisiert).

---

## 4. Value Alpha Potential (Kategorie: Value)

### Business-Problem
Welche Aktien sind aktuell am weitesten unter ihrem eigenen historischen Outperformance-Hoch? Mean-Reversion-Annahme: was stark outperformt hat, kehrt dazu zurück.

### Formel

```
Input:  prices: pd.DataFrame  (index=Datum, columns=Ticker, ~1.5 Jahre Tagespreise)

Benchmark = prices.mean(axis=1)           # Equal-Weighted Universe

# Schritt 1: Rolling 63-Tage-Alpha
horizon = 63
alpha = prices.pct_change(horizon).sub(
    prices.mean(axis=1).pct_change(horizon), axis=0
)

# Schritt 2: Rolling Maximum über 252 Tage (1 Jahr)
rolling_max_alpha = alpha.rolling(window=252, min_periods=68).max()

# Schritt 3: Distance to Peak
potential = rolling_max_alpha − alpha      # wie weit unter dem Hoch?

# Schritt 4: Snapshot + Ranking
score = potential.iloc[-1]
rank  = score.rank(ascending=False, method="min").astype(int)
```

**Horizonte**: Alpha-Horizont 63d (konsistent mit Trend Momentum); Rolling-Max 252d (1 Jahr — genug für echte Peaks, nicht zu stale).

### Edge-Cases
- **< 68 Datenpunkte** (`min_periods` für rolling max): `rank=None`, `confidence="low"`.
- **Negativer potential**: Aktuelles Alpha über Rolling-Max (neuer Peak heute) → gültiger Score, wird normal gerankt.
- **Kein Fundamental-Check**: kann gefallene Junk-Stocks ranken — Aggregator balanciert das durch Quality + Diversification.

### Test-Approach
- **Golden Dataset**: Ticker A hat Rolling-Max-Alpha +10%, aktuell +2% → potential=8%. Ticker B konstant bei 0% → potential=0%. A muss `rank=1`.
- **Negativer Potential**: Ticker auf neuem Outperformance-Hoch → Score < 0, trotzdem gerankt.
- **min_periods**: Ticker mit 50 Datenpunkten → `rank=None`.
- **Deterministisch**.

### Performance
< 150 ms für 500 Ticker × 400 Tage.

---

## 5. Diversification (Kategorie: Risk)

### Business-Problem
Welche Aktien weisen die niedrigste Eigenvolatilität und die geringste Korrelation zu anderen Titeln im Universum auf? Belohnt diversifikationsfreundliche, risikoarme Titel.

### Formel

```
Input:  prices: pd.DataFrame  (index=Datum, columns=Ticker, ~1 Jahr Tagespreise)

returns = prices.pct_change().dropna()

# Kovarianzmatrix mit Ledoit-Wolf-Shrinkage (scikit-learn)
from sklearn.covariance import LedoitWolf
lw = LedoitWolf().fit(returns)
cov_matrix = pd.DataFrame(lw.covariance_, index=tickers, columns=tickers)

# Korrelationsmatrix
std_devs   = np.sqrt(np.diag(cov_matrix))
corr_matrix = cov_matrix / np.outer(std_devs, std_devs)

# Je Ticker
volatility       = std_devs * np.sqrt(252)             # annualisiert
avg_correlation  = (corr_matrix.sum(axis=1) - 1) / (n - 1)  # ohne Selbstkorrelation

# Score: monoton fallend in (volatility + avg_correlation)
# → niedrige Vola + niedrige Korrelation ergibt höheren Score → Rang 1
# (Faktor 2 ist nur Skalierung, hat keinen Effekt aufs Ranking;
#  die Formel ist NICHT das harmonische Mittel — HM(a,b) = 2ab/(a+b).)
score = 2 / (volatility + avg_correlation)

rank = pd.Series(score).rank(ascending=False, method="min").astype(int)
```

### Edge-Cases
- **n = 1 Ticker**: Korrelation nicht definierbar → `rank=1`, `confidence="low"`.
- **n = 2 Ticker**: Korrelation = 1.0 (identische Reihe) oder −1.0 → Ledoit-Wolf stabil, Score normal berechnen.
- **Ticker mit 0-Varianz** (alle Returns = 0): `std_dev=0` → Division durch 0 in Score → `rank=None`, `confidence="low"`.
- **< 30 Datenpunkte**: Ledoit-Wolf instabil → `rank=None` für alle.
- **Leeres Universum**: Rückgabe `[]`.

### Test-Approach
- **Golden Dataset**: 3 Ticker — A (niedrige Vola, niedrige Korrelation), B (mittlere), C (hohe Vola, hohe Korrelation) → A muss `rank=1`, C `rank=3`.
- **Konstruierter DataFrame**: `np.random.seed(42)` für Reproduzierbarkeit.
- **Einzelticker-Edge-Case**: 1 Ticker → `rank=1`.
- **Deterministisch**: gleicher Seed → gleiche Ränge.

### Performance
< 500 ms für 500 Ticker × 252 Tage (Ledoit-Wolf ist O(n²) in der Anzahl Ticker).

---

## 6. Gemeinsame Konventionen

### Daten-Interface
```python
# Fundamentals-Modelle (Quality Classic)
UniverseData = dict[str, dict[str, float | None]]

# Preis-Modelle (Alpha, Trend Momentum, Value Alpha Potential, Diversification)
# prices: pd.DataFrame — index=pd.DatetimeIndex (UTC), columns=Ticker-Symbole
# Keine NaN in der Mitte erlaubt; am Anfang/Ende durch min_periods behandelt
```

### Ranking-Konvention
- Rang 1 = beste Aktie laut diesem Modell
- Gleichstand → gleicher Rang (method="min"), nächster Rang springt
- Ticker ohne auswertbare Daten: `rank=None`, `confidence="low"`

### Konfidenz
| Wert | Bedeutung |
|------|-----------|
| `"high"` | alle oder die meisten Kennzahlen/Datenpunkte verfügbar |
| `"low"` | < 50% der Kennzahlen verfügbar oder `rank=None` |
