# Spec: BacktestService — Light (MVP-Slice)

**Status**: Draft v1.0 — 2026-05-12
**Rolle**: A — Quant Core (Fabia)
**Parent-Spec**: `docs/specs/2026-04-21-prisma-capstone-design.md` §7.4 + §9.5
**Spec-Konvention**: AGENTS.md §3 "Wenn ein neues Quant-Modell/Service implementiert wird"

---

## 1. Zweck

Implementiert die Light-Variante des `BacktestService` aus Design-Spec §7.4. Erlaubt einem User, einen abgeschlossenen `ModelRun` als Startpunkt zu nehmen und das resultierende Top-N-Portfolio über einen Zeitraum gegen zwei Benchmarks zu vergleichen. Liefert annualisierte Rendite, annualisierte Volatilität, Sharpe-Ratio und Maximum Drawdown.

**Slicing-Begründung:** Die "echte" Backtest-Variante mit monatlichem Re-Ranking (RankingService N-mal über die History laufen lassen) ist 5-10× komplexer und braucht ein Snapshot-Konzept für Universe + Prices zu jedem Rebalancing-Datum. Die Light-Variante validiert Entity, Repository, REST-Endpoints, Metriken-Berechnung und Frontend-Anbindung Ende-zu-Ende und ist damit auch das Capstone-Demo-Asset (Spec §14.3 Z. 649: "Backtest starten → Chart mit 3 Kurven").

---

## 2. Scope

### In Scope

- `BacktestService.run_backtest(universe_id, model_run_id, start_date, end_date, top_n)` und `.get_backtest_result(id)`
- `BacktestResult`-Entity + ORM + Alembic-Migration
- `BacktestResultRepository` (Port + SQLA-Adapter)
- 3 simulierte Portfolios, alle gleichgewichtet, monatlich rebalanciert (Reset auf Equal-Weight):
  | Portfolio | Beschreibung |
  |---|---|
  | PRISMA Top-N | Top-N aus dem übergebenen ModelRun, EW |
  | Equal-Weight Universe | Alle Ticker im Universe, EW |
  | Benchmark | `^SSMI` (Default, konfigurierbar via Request) — über `MarketDataProvider` |
- Metriken (alle annualisiert): Total Return, CAGR, Volatilität, Sharpe (rf=0), Max Drawdown
- 2 REST-Endpoints: `POST /api/v1/backtests/run`, `GET /api/v1/backtests/{id}`
- Pydantic-Request/Response-Schemas
- Test-Stack: Unit (Service-Logik + Metriken), Integration (REST + Repository), Golden-Dataset

### Out of Scope (Folge-Slices)

- **Monatliches Re-Ranking**: RankingService bei jedem Rebalancing-Datum neu auf History laufen lassen. Erfordert eigenes Spec-Slice mit Snapshot-Konzept.
- **Walk-Forward-Analyse** (Design-Spec §17 Backlog Z. 799)
- **Transaktionskosten-Modell** (Design-Spec §17 Backlog Z. 800)
- **Universe-Drift während Backtest-Periode**
- **Asynchroner Run** (Light-Variante: sync, ggf. <30s — Universe ≤50 Ticker, 5J-Window)
- **Backtest-zu-Backtest-Vergleich** (mehrere Runs in einer UI-View)

---

## 3. Architektur

### Dateistruktur

```
backend/
├── application/services/
│   └── backtest_service.py                # NEU
├── domain/
│   ├── entities/
│   │   └── backtest_result.py             # NEU
│   └── repositories/
│       └── backtest_result_repository.py  # NEU (Port)
├── infrastructure/persistence/
│   ├── models/
│   │   └── backtest_result.py             # NEU (ORM)
│   ├── repositories/
│   │   └── backtest_result_repository.py  # NEU (SQLA-Adapter)
│   └── alembic/versions/
│       └── 000X_create_backtest_results.py # NEU — Nummer = nächste freie nach
│                                          #        Merge von PR #70 (memo_batch_jobs)
│                                          #        und PR #79 (pgvector + embeddings)
│                                          #        Aktuell vermutlich 0009 oder 0010.
└── interfaces/rest/
    ├── routers/backtests.py               # NEU
    └── dependencies.py                    # ERWEITERT (Repository + Service)
```

### Komponenten-Verantwortung

| Komponente | Verantwortung | Tests |
|---|---|---|
| `BacktestService` | Orchestriert: Top-N aus ModelRun laden → Preise via MarketDataProvider → 3 Portfolios simulieren → Metriken berechnen → Persistieren. | Unit (Service mit Mock-Repos) + Integration (PG) |
| `BacktestResult` | Pydantic-Entity mit typisierten Sub-Schemata `PortfolioMetrics` + `BacktestSeries` (siehe §8), dates, top_n, universe_id, model_run_id. | Unit |
| `BacktestResultRepository` | Domain-Port + SQLA-Adapter (`save`, `get`). UPSERT auf `(model_run_id, start_date, end_date, top_n, benchmark_ticker)` — v1.1: `benchmark_ticker` mit aufgenommen, sonst kollidieren zwei Runs mit unterschiedlichen Benchmarks ungewollt. | Integration (PG) |
| `backtests.py`-Router | REST-Endpoints, FastAPI-DI, Pydantic-Request/Response. | Integration (FastAPI TestClient) |

---

## 4. Data Flow

```
POST /api/v1/backtests/run
{ model_run_id, start_date, end_date, top_n=10, benchmark_ticker="^SSMI" }
  │
  ▼
BacktestService.run_backtest(...)
  │
  ├─ 1. Validate inputs (siehe §11 v1.1: `universe_id` aus Request entfernt — wird aus `model_run.universe_id` abgeleitet, eliminiert Validation-Lücke "fremdes Universe"):
  │     - model_run_id existiert (404 falls nein) → universe_id = model_run.universe_id
  │     - universe existiert (Sanity-Check, sollte via FK garantiert sein)
  │     - start_date < end_date, beide ≤ today
  │     - top_n > 0, top_n ≤ universe.stock_count
  │     - end_date - start_date ≥ 30 Tage (sonst Metriken unzuverlässig)
  │
  ├─ 2. Top-N-Tickers laden:
  │     run_repo.get_total_ranks(model_run_id)
  │     → Sortieren nach total_rank, ersten top_n nehmen
  │
  ├─ 3. Universe-Tickers laden + Benchmark-Ticker hinzufügen:
  │     all_tickers = universe.tickers ∪ {benchmark_ticker}
  │
  ├─ 4. Prices fetch (parallel):
  │     market_data.get_prices_range(all_tickers, start_date, end_date)
  │     → DataFrame mit DatetimeIndex (Trading-Days) und Ticker-Spalten
  │     → 404 wenn weniger Trading-Days als 20 vorhanden
  │
  ├─ 5. 3 Portfolios simulieren (siehe §5):
  │     prisma_series   = _simulate_portfolio(prices[top_n_tickers], rebalance="monthly")
  │     universe_series = _simulate_portfolio(prices[universe.tickers], rebalance="monthly")
  │     benchmark_series = prices[benchmark_ticker] / prices[benchmark_ticker].iloc[0]
  │
  ├─ 6. Metriken berechnen je Portfolio (siehe §6)
  │
  ├─ 7. Persist:
  │     result = BacktestResult(
  │         id=uuid4(), universe_id, model_run_id, start_date, end_date, top_n,
  │         benchmark_ticker,
  │         metrics={
  │             "prisma":    {...},
  │             "universe":  {...},
  │             "benchmark": {...}
  │         },
  │         series={
  │             "dates":     [iso-strings],
  │             "prisma":    [floats],
  │             "universe":  [floats],
  │             "benchmark": [floats]
  │         },
  │         created_at=now(UTC),
  │     )
  │     await backtest_repo.save(result)
  │
  └─ return result
```

---

## 5. Portfolio-Simulation

### `_simulate_portfolio(prices: pd.DataFrame, rebalance: Literal["monthly"]) -> pd.Series`

Equal-Weight-Portfolio mit periodischem Reset-auf-Equal-Weight:

```python
# Pseudocode
returns = prices.pct_change().fillna(0)  # Tagesrenditen pro Ticker
n = len(prices.columns)
weights = np.full(n, 1/n)  # Start: 1/N pro Ticker
portfolio_returns = []
rebalance_dates = _monthly_rebalance_dates(prices.index)

for date in prices.index:
    daily_return = (weights * returns.loc[date]).sum()
    portfolio_returns.append(daily_return)
    # Update weights nach Tagesrendite (Drift)
    weights = weights * (1 + returns.loc[date])
    weights = weights / weights.sum()  # Re-normalisieren auf 100%
    # Monatliches Rebalancing: Reset auf Equal-Weight
    if date in rebalance_dates:
        weights = np.full(n, 1/n)

return (1 + pd.Series(portfolio_returns, index=prices.index)).cumprod()
```

**`_monthly_rebalance_dates(idx: pd.DatetimeIndex) -> set[pd.Timestamp]`** (v1.1, war ungespezifiziert):

```python
def _monthly_rebalance_dates(idx: pd.DatetimeIndex) -> set[pd.Timestamp]:
    """Letzter Trading-Day jedes Kalendermonats im Index.

    Gängige Konvention, deterministisch aus dem Index ableitbar — keine
    Holiday-Calendar-Annahmen. Implementation: pandas Grouper auf Monats-Ebene.
    """
    grouped = pd.Series(idx, index=idx).groupby(pd.Grouper(freq="ME"))
    return set(grouped.last().dropna())
```

**Edge-Cases:**
- **Statisches Universe Annahme** (v1.1, war implizit): Tickers müssen für die *ganze* Backtest-Periode gelistet sein. Late-Listings produzieren **Look-Ahead-Bias** — ein Ticker bekommt seinen 1/N-Anteil bevor er existiert, weil `pct_change().fillna(0)` für Pre-Listing-Tage 0%-Returns liefert aber `weights[i] = 1/N` trotzdem auf den Ticker angewandt wird. Out-of-scope für MVP — Validierung via §2 In-Scope-Annahme "statisches Universe während Backtest-Periode". Folge-Slice mit Walk-Forward-Universe muss das adressieren.
- Ticker mit Konkurs / Delisting in der History → letzter verfügbarer Preis wird forward-gefüllt (`prices.ffill()` vor `pct_change()`). Approximation, OK für MVP.
- Weniger als 1 voller Monat zwischen start_date und end_date → kein Rebalancing, reine Drift.

---

## 6. Metriken

Für jede Portfolio-Reihe `series: pd.Series` (kumulierte Werte beginnend bei 1.0):

```python
def _compute_metrics(series: pd.Series) -> dict[str, float]:
    n_days = len(series)
    years = n_days / 252.0

    total_return = series.iloc[-1] / series.iloc[0] - 1.0
    cagr = (series.iloc[-1] / series.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    daily_returns = series.pct_change().dropna()
    annual_vol = daily_returns.std() * np.sqrt(252)
    sharpe = (cagr / annual_vol) if annual_vol > 0 else 0.0  # rf=0

    cummax = series.cummax()
    drawdown = (series - cummax) / cummax
    max_drawdown = float(drawdown.min())

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annual_vol": float(annual_vol),
        "sharpe": float(sharpe),
        "max_drawdown": max_drawdown,
    }
```

**Konventionen:**
- `rf=0` für Sharpe (vereinfachend; Spec §17 Z. 776 erlaubt Default-Annahmen)
- `252` Trading-Days/Jahr (konsistent mit Diversification-Spec)
- Negative CAGR-Werte sind erlaubt (Bear Markets)
- `sharpe` ohne Vol-Schutz: wenn Vol=0, Sharpe=0 (statt division by zero)

---

## 7. REST-Endpoints

### `POST /api/v1/backtests/run`

```jsonc
// Request (v1.1: universe_id entfernt — wird aus model_run.universe_id abgeleitet)
{
  "model_run_id": "550e8400-e29b-41d4-a716-446655440001",
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "top_n": 10,
  "benchmark_ticker": "^SSMI"  // optional, default "^SSMI"
}

// 200 Response (kompletter BacktestResult, siehe §4 Schritt 7)
```

**Status-Codes:**
- `200`: Backtest erfolgreich
- `400`: Validierungs-Fehler (z.B. start_date ≥ end_date, top_n > universe.size)
- `404`: ModelRun nicht gefunden
- `422`: Pydantic-Schema-Fehler
- `500`: Stub-MarketDataProvider liefert leeren DataFrame (Bug, sollte nicht passieren)
- `503`: Echter MarketDataProvider (yfinance, Folge-Slice) unerreichbar / Rate-Limit

### `GET /api/v1/backtests/{id}`

- `200`: Backtest-Result existiert
- `404`: nicht gefunden

---

## 8. Entity + Pydantic-Schemas

```python
# backend/domain/entities/backtest_result.py

class PortfolioMetrics(BaseModel):
    """Annualisierte Kennzahlen pro Portfolio (siehe §6)."""
    total_return: float
    cagr: float
    annual_vol: float
    sharpe: float
    max_drawdown: float


class BacktestSeries(BaseModel):
    """Zeitreihen-Block, alle 4 Listen identisch lang (Validator)."""
    dates: list[date]
    prisma: list[float] = Field(..., description="Portfolio-Wert PRISMA Top-N, normiert auf 1.0 am start_date")
    universe: list[float]
    benchmark: list[float]

    @model_validator(mode="after")
    def _lengths_match(self) -> "BacktestSeries":
        n = len(self.dates)
        if not (len(self.prisma) == n and len(self.universe) == n and len(self.benchmark) == n):
            raise ValueError(f"series-Listen müssen gleich lang sein (dates={n}, prisma={len(self.prisma)}, ...)")
        if any(v < 0 for v in (*self.prisma, *self.universe, *self.benchmark)):
            raise ValueError("Portfolio-Werte können nicht negativ werden")
        return self


class BacktestResult(BaseModel):
    id: UUID
    universe_id: UUID
    model_run_id: UUID
    start_date: date
    end_date: date
    top_n: int = Field(..., ge=1, le=100)
    benchmark_ticker: str = Field(..., max_length=20)
    metrics: dict[Literal["prisma", "universe", "benchmark"], PortfolioMetrics]
    series: BacktestSeries
    created_at: datetime
```

**Validierung** (v1.1: getypte Sub-Schemata statt `dict[str, list]` — Pydantic-validiert + Frontend-TypeScript-generierbar):
- `BacktestSeries`-Validator stellt sicher: alle 4 Listen gleich lang, alle Werte ≥ 0
- `metrics`-dict ist typisiert auf die 3 Portfolio-Schlüssel (Literal)
- `top_n` ≤ 100 (Sanity-Cap)

---

## 9. Test-Strategie

### 9.1 Unit-Tests (`backend/tests/unit/`)

| Datei | Was getestet wird |
|---|---|
| `test_backtest_service.py` | 5 Pfade mit Mock-Repos: (1) Happy-Path mit 5-Ticker-Universe + Top-3, deterministische Preise; (2) Top-N > universe.size → 400; (3) start_date ≥ end_date → 400; (4) Universe nicht gefunden → 404; (5) MarketDataProvider liefert leeren DataFrame → 503 |
| `test_backtest_metrics.py` | Golden-Dataset für `_compute_metrics`: konstante 10% Jahres-Performance → CAGR≈0.10, Vol≈0, Sharpe=0, MaxDD=0. Eine 50%-Drawdown-Reihe → MaxDD≈-0.50 |
| `test_backtest_portfolio_simulation.py` | `_simulate_portfolio` deterministisch — zwei Scharfschuss-Tests: (a) 2 Ticker × 2 Monate, Reset auf 50/50 nach Monatsende verifizieren; (b) **v1.1: Drift-Mathematik gegen Handrechnung** — 2 Assets × 5 Tage mit deterministischen Returns (+10%/-5%/+5%/-2%/+1%), Portfolio-Value-Verlauf gegen vorab gerechnete Werte prüfen. Fängt Regression bei späterer Vectorize-Refaktorierung. |
| `test_backtest_result_entity.py` | Pydantic-Validation: ungleiche Series-Längen → ValidationError, top_n > 100 → ValidationError, negative Portfolio-Werte → ValidationError |

### 9.2 Integration-Tests (`backend/tests/integration/`)

| Datei | Was getestet wird |
|---|---|
| `test_backtest_service_integration.py` | Echte PG (Testcontainers) + Stub-MarketDataProvider mit kalibrierten Preisen. End-to-End: POST → DB → GET → Response-Shape |
| `test_backtests_endpoint.py` | FastAPI TestClient: POST happy, POST 400 (invalid), GET 200, GET 404 |

### 9.3 Golden-Dataset

`backend/tests/fixtures/backtest/perfect_strategy.json`:
- 5 Ticker × 36 Monate, deterministische Preisreihen
- Die Fixture **konstruiert die Preise so**, dass die 3 niedrig-Vola-Tickers im `model_run.results` an Top-3 stehen (BacktestService sortiert nicht selbst nach Vola — er nimmt die Top-N aus dem Run)
- Erwartete Metriken vorab via NumPy berechnet und im Fixture-File abgelegt
- Test prüft Metrik-Übereinstimmung mit **±0.5%-Toleranz** — bei `cumprod` über 36 Monate akkumuliert Floating-Point-Drift, ±0.1% wäre CI-Flake-gefährdet (v1.1: erst messen, dann Toleranz konkret begründen — initial 0.5%, kann nach erstem grünen Run verschärft werden)

### 9.4 Coverage-Ziel

- Unit: ≥90% (Service + Helpers)
- Integration: ≥80%
- Gesamtsuite: bleibt ≥80% per `fail_under` (PR #83)

---

## 10. Akzeptanz-Kriterien

Implementation ist komplett, wenn:

- [ ] `BacktestResult`-Entity (Pydantic v2, UTC-aware) in `backend/domain/entities/`
- [ ] `BacktestResultRepository`-Port + SQLA-Adapter mit UPSERT-Logik
- [ ] Alembic-Migration `000X_create_backtest_results` (reversibel) — Nummer = nächste freie nach Merge von #70 + #79 (siehe Risk in §10)
- [ ] `BacktestService` mit `run_backtest` und `get_backtest_result` (siehe §3)
- [ ] `_simulate_portfolio` mit monatlichem Reset-Rebalancing (siehe §5)
- [ ] `_compute_metrics` mit allen 5 Metriken (siehe §6)
- [ ] `POST /api/v1/backtests/run` und `GET /api/v1/backtests/{id}` live, in OpenAPI-Schema sichtbar
- [ ] Alle Tests aus §9.1 und §9.2 grün
- [ ] Golden-Dataset-Metriken matchen Spec-Erwartungen (initial ±0.5%, nach erstem grünen Run ggf. verschärfen)
- [ ] Coverage neue Module ≥85%; Gesamtsuite bleibt ≥80% (CI-Gate aus PR #83)
- [ ] mypy strict + ruff clean
- [ ] Sample-Backtest-Result unter `docs/examples/backtest-result-sample.json`
- [ ] AI-USAGE.md-Eintrag (40%-Achse Capstone)
- [ ] README-Sektion "Backtest" mit Kurz-Anleitung (Curl-Example)

---

## 11. Bewusste Abweichungen von Parent-Spec

### 11.1 Was die Light-Variante NICHT ist (v1.1 Aufmacher per #85-Review S3)

**WICHTIGSTE Abweichung von Design-Spec §7.4**: Diese Slice macht **KEIN echtes Re-Ranking pro Monat**. "Monatliches Rebalancing nach Total Rank" wird interpretiert als **Reset auf Equal-Weight der Top-N** — der RankingService wird nicht erneut auf historischen Preisen ausgeführt.

**Konkret**:
- ✅ Wir nehmen *eine* `model_run_id` als Ausgangspunkt (typisch: aktueller Run)
- ✅ Wir extrahieren die Top-N-Ticker daraus
- ✅ Wir simulieren das Halten dieser N Ticker über die historische Periode mit monatlichem Equal-Weight-Reset
- ❌ Wir laufen NICHT 36×RankingService für 36 Monate Backtest
- ❌ Wir berücksichtigen NICHT dass die Top-N sich über die Zeit verändert hätten

**Folge-Slice "echtes Re-Ranking"** braucht: Historical-Snapshot von Universe + Prices zu jedem Rebalancing-Datum, plus die Garantie dass alle 5 Quant-Modelle deterministisch auf historischen Daten laufen. Aufwand: 5-10× Light-Slice. **Nicht in MVP-Scope** — Spec §17 Backlog.

### 11.2 Weitere bewusste Abweichungen

| Parent-Spec-Stelle | Slice-Verhalten | Begründung |
|---|---|---|
| §9.5 — `run_backtest` Input nur `(Universe-ID, Start/End, Top-N)` | Input: `(model_run_id, Start/End, Top-N, benchmark_ticker)` — **`universe_id` entfernt** (v1.1 per #85-Review I3) | `model_run_id` enthält die Universe-Info schon; `universe_id` separat würde Validation-Lücke "fremdes Universe" öffnen. `benchmark_ticker` als Default `^SSMI` + Konfig-Override. |
| §10.1 — Endpoint-Path | `/api/v1/backtests/run` und `/api/v1/backtests/{id}` | Konsistent mit den anderen Service-Pfaden (`/api/v1/...`). |
| §14.3 — "Chart mit 3 Kurven" | 3 Portfolios: PRISMA Top-N + Universe-EW + Benchmark | Spec lässt offen welche 3. Diese Wahl bildet die "lohnt sich der Ranking-Aufwand?"-Frage (vs. Universe-EW als Naivität, vs. Benchmark als Markt-Baseline) am sinnvollsten ab. |

### 11.3 Performance-Ziel (v1.1 Konsolidierung per #85-Review S4)

| Provider | Ziel | Realität |
|---|---|---|
| StubMarketDataProvider | < 2s für 5J-Backtest, 5 Ticker | MVP-Default |
| YFinanceMarketDataProvider (Folge-Slice) | < 30s für 5J-Backtest, 5 Ticker | Sync ist dann Grenze — Async/Job-Queue ab da nötig |

---

## 12. Offene Punkte vor Plan-Schreiben

1. **Sync vs. Async**: siehe §11.3 (Performance-Ziel) — Sync für MVP, Async für Folge-Slice.
2. **Universe-Drift**: aktueller Slice ignoriert, dass ein Universe im Lauf der Zeit hinzugefügte/entfernte Ticker hat. Implementation nutzt das *aktuelle* Universe für die ganze Backtest-Periode. Akzeptabel für Light-Variante.
3. **Benchmark-Datenquelle**: `^SSMI` kommt über den gleichen `MarketDataProvider` — Stub liefert für unbekannte Ticker einen 100-Random-Walk. Für die echte Demo brauchts ggf. einen separaten Index-Adapter. Folge-Slice.
4. **Migration-Nummern-Kollision** (v1.1 per #85-Review I4): PR #70 belegt `0007`, PR #79 belegt `0008` (geplant 0009 nach Split). Diese Spec sagt explizit "nächste freie Nummer nach Merge von #70+#79" — konkret zugewiesen erst im Plan-Schreib-Schritt, nicht hier hartkodiert.

---

## 13. Änderungshistorie

| Version | Datum | Autor | Änderung |
|---|---|---|---|
| Draft v1.0 | 2026-05-12 | Fabia / Claude Code Opus 4.7 | Initiale Slice-Spec — BacktestService Light, schneidet Monthly-Re-Ranking und Walk-Forward bewusst heraus |
| Draft v1.1 | 2026-05-13 | Fabia / Claude Code Opus 4.7 | Sheylas Review-Findings (PR #85) eingearbeitet: I1 `_monthly_rebalance_dates` spezifiziert (letzter Trading-Day jedes Monats, Pseudocode in §5); I2 Late-Listing-Look-Ahead-Bias explizit in §5 Edge-Cases dokumentiert; I3 `universe_id` aus Request entfernt — wird aus `model_run.universe_id` abgeleitet (§4, §7, §11.2); I4 Migration-Nummer auf "nächste freie nach #70+#79" (§3, §10, §12); S1 `BacktestSeries` + `PortfolioMetrics` als typisierte Sub-Schemata (§8); S2 `benchmark_ticker` in UPSERT-Key aufgenommen (§3 Komponenten-Tabelle); S3 Kernabweichung als §11.1-Aufmacher prominent gemacht; S4 Performance-Ziel in §11.3 konsolidiert; S5 Drift-Mathematik-Test in §9.1 ergänzt; S6 Toleranz auf ±0.5% mit Begründung. N1 Stub-Empty-Response auf 500 + echtem-Provider-Fail auf 503 aufgesplittet; N2 §9.3-Formulierung präzisiert. |
