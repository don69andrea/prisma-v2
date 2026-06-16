# Spec: RankingService — Multi-Model-Wiring (alle 5 Modelle)

**Status: Final**
**Datum: 2026-05-09**
**Autor: Fabia Holzer / Claude Code**
**Bezieht sich auf**: `docs/specs/2026-04-21-prisma-v2-design.md` §6, `docs/specs/2026-04-28-quant-mvp-models.md`

---

## Übersicht

Aktuell ruft `RankingRunService` nur `QualityClassicModel` auf — die 4 anderen Modelle (Diversification, Trend Momentum, Value Alpha Potential, Alpha) sind als Domain-Klassen implementiert, aber **nicht im Service verdrahtet**. Diese Spec schließt die Lücke: ein neuer `MarketDataProvider`-Port (analog `FundamentalsProvider`), ein `StubMarketDataProvider` für Demo/Tests, und der Service ruft alle 5 Modelle auf.

**Out of Scope** (jeweils Folge-PRs):
- Echter `YFinanceMarketDataProvider`-Adapter (mit Rate-Limit, Caching).
- REST-Endpoint-Anpassungen (`POST /api/v1/runs` bleibt API-kompatibel).
- Konfigurierbare `lookback_days` (fix 504 Trading-Days).
- Threshold-basiertes Run-Failure (Verhalten bleibt fail-soft).

---

## Architektur

Saubere Erweiterung des existierenden Provider-Patterns. **Keine** Änderungen an Domain-Modellen, Aggregator, Repositories oder REST-Layer.

```
backend/
  domain/
    ports/
      fundamentals_provider.py      (existiert)
      market_data_provider.py       (NEU)
  infrastructure/
    providers/
      stub_fundamentals.py          (existiert)
      stub_market_data.py           (NEU)
  application/services/
    ranking_run_service.py          (erweitert: nutzt beide Ports + alle 5 Modelle)
```

---

## Port-Interface

```python
# backend/domain/ports/market_data_provider.py
from abc import ABC, abstractmethod
import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        """Liefert Tagesschlusskurse für 504 Trading-Days bis zum letzten verfügbaren Tag.

        Returns:
            DataFrame mit:
            - Index: pd.DatetimeIndex, **tz-aware (UTC)**, Business-Day-Frequenz
            - Columns: nur tickers, für die Daten verfügbar sind (Best-Effort)
            - Shape: 504 × N (N ≤ len(tickers))
            - Keine NaN in der Mitte; Anfang/Ende kann lückig sein wenn Ticker neu/delisted
            - Empty DataFrame wenn `tickers=[]`
        """
        ...
```

### Vertrag

| Aspekt | Garantie |
|---|---|
| Index-Typ | `pd.DatetimeIndex`, `tz="UTC"` |
| Index-Frequenz | Business-Day (Mo–Fr, ohne Holidays) |
| Index-Länge | exakt `_TRADING_DAYS = 504` (entspricht ~2 Kalenderjahren) |
| Spalten | nur Tickers mit Daten; unbekannte/delisted Ticker werden weggelassen |
| Werte | Tagesschlusskurse als `float64`; keine NaN in der Mitte |
| Empty-Input | `get_prices([])` → leere `pd.DataFrame()` |

---

## Stub-Adapter

```python
# backend/infrastructure/providers/stub_market_data.py
import zlib
import numpy as np
import pandas as pd

from backend.domain.ports.market_data_provider import MarketDataProvider

_TRADING_DAYS: int = 504
_DRIFT: float = 0.0005
_VOLATILITY: float = 0.015
_START_PRICE: float = 100.0


class StubMarketDataProvider(MarketDataProvider):
    """Demo/Test-Provider. Pro Ticker deterministischer Random-Walk.

    Design-Entscheidungen:
    - **Seed = zlib.crc32(ticker.encode("utf-8"))**, NICHT builtin `hash()`.
      Python-Hash-Randomization würde sonst pro Prozess-Start andere
      Random-Walks erzeugen → nicht-deterministische Tests.
    - **`end_date` injizierbar** (default `pd.Timestamp.now(tz="UTC").normalize()`).
      Tests übergeben fixed end_date für vollständige Determinismus —
      sonst ändert sich der Index täglich.
    - **`tz="UTC"`**: CLAUDE.md-Konvention "Datumshandling ohne Timezone
      → immer UTC-aware" wird hier wörtlich umgesetzt.
    """

    def __init__(self, end_date: pd.Timestamp | None = None) -> None:
        self._end_date = end_date or pd.Timestamp.now(tz="UTC").normalize()

    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame()

        index = pd.bdate_range(end=self._end_date, periods=_TRADING_DAYS, tz="UTC")

        data: dict[str, np.ndarray] = {}
        for ticker in tickers:
            seed = zlib.crc32(ticker.encode("utf-8"))
            rng = np.random.default_rng(seed)
            returns = rng.normal(_DRIFT, _VOLATILITY, _TRADING_DAYS)
            prices = _START_PRICE * (1 + returns).cumprod()
            data[ticker] = prices

        return pd.DataFrame(data, index=index)
```

### Beispiel-Output

```python
>>> stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
>>> df = await stub.get_prices(["AAPL", "MSFT", "GOOGL"])
>>> df.shape
(504, 3)
>>> df.index.tz
datetime.timezone.utc
>>> df.iloc[-1]   # letzter Handelstag
AAPL     127.43
MSFT      94.21
GOOGL    156.07
```

---

## Service-Änderungen

### Konstruktor

```python
def __init__(
    self,
    universe_repo: UniverseRepository,
    run_repo: RankingRunRepository,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,   # NEU
) -> None:
    self._universe_repo = universe_repo
    self._run_repo = run_repo
    self._fundamentals_provider = fundamentals_provider
    self._market_data_provider = market_data_provider
```

### Daten-Fetch (parallel via `asyncio.gather`)

```python
import asyncio

# In create_and_execute_run:
fundamentals, prices = await asyncio.gather(
    self._fundamentals_provider.get_fundamentals(list(universe.tickers)),
    self._market_data_provider.get_prices(list(universe.tickers)),
)

per_model = {
    "quality_classic":       QualityClassicModel().run(fundamentals),
    "diversification":       DiversificationModel().run(prices=prices),
    "trend_momentum":        TrendMomentumModel().run(prices=prices),
    "value_alpha_potential": ValueAlphaPotentialModel().run(prices=prices),
    "alpha":                 AlphaModel().run(prices=prices),
}
total_results = RankingAggregator().aggregate(per_model, weights)

# results-Dict-Aufbau wie bisher, nur per_model_ranks bekommt 5 Keys statt 1
```

### Modell-Aufrufe **ohne** Try/Except

Per CLAUDE.md: *"Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code and framework guarantees."* Modelle haben ihre eigenen Edge-Cases (`empty universe`, `<MIN_DATAPOINTS`, etc.) bereits robust behandelt. Wenn ein Modell crashed, ist das ein echter Bug — soll bubbeln, nicht in `failed`-Stati versteckt werden.

---

## Daten-Fluss

```
Universe (DB)
     │
     ▼
asyncio.gather(
    fundamentals_provider.get_fundamentals(tickers),    ← parallel
    market_data_provider.get_prices(tickers),
)
     │
     ▼
5 Modelle synchron (reine CPU, keine awaits)
     │
     ▼
RankingAggregator.aggregate(per_model, weights)
     │
     ▼
Repository.save_results(...)
```

---

## Error-Handling

**Best-Effort** (analog `FundamentalsProvider`):

- Provider liefert nur Spalten für tatsächlich verfügbare Ticker.
- Unbekannte/delisted/nichtssagende Ticker fehlen in der DataFrame.
- Modelle markieren betroffene Ticker via `rank=None, confidence="low"` (Standard-Pattern aus den Modell-Specs).
- Aggregator propagiert `rank=None` korrekt durch (existierendes Verhalten).
- Ein einzelner fehlender Ticker bringt **nie** den ganzen Run zum Failen.

**Hard Failures** (bubbeln zu `run.status = "failed"` durch existierenden Repository-Pfad):
- Network-Outage in echtem yfinance-Adapter (separate PR).
- DB-Fehler.
- Programmierfehler in einem Modell (sollte nie passieren — Test-Coverage ist da).

---

## Test-Strategie

**TDD-Pflicht** (CLAUDE.md): jeder neue Code wird Test-First entwickelt.

### Unit-Tests

`backend/tests/unit/infrastructure/test_stub_market_data.py`:

| Test | Verifiziert |
|---|---|
| `test_returns_dataframe_with_expected_shape` | Shape = (504, N), Index tz-aware UTC |
| `test_deterministic_across_runs` | Selber Ticker → identische Reihe (proof: `zlib.crc32`-Fix vs. builtin `hash()`) |
| `test_end_date_is_injectable` | Fixed `end_date` → fixed Index (proof: zeitabhängige-Tests-Fix) |
| `test_empty_tickers_returns_empty_df` | Edge-Case |
| `test_unknown_ticker_still_gets_random_walk` | Stub kennt jeden Ticker via Hash-Seed |
| `test_returns_finite_positive_prices` | Keine NaN/Inf, alle > 0 |

### Integration-Tests

`backend/tests/integration/test_ranking_run_service_multi_model.py`:

| Test | Verifiziert |
|---|---|
| `test_run_with_all_five_models_produces_per_model_ranks` | `per_model_ranks` enthält Keys für alle 5 Modelle |
| `test_sweet_spot_triggers_with_five_models` | Manche Ticker in Top-25% von ≥3 Modellen → `is_sweet_spot=True` |
| `test_run_with_empty_prices_falls_back_to_quality_only` | Prices-Provider liefert leere DataFrame → Quality-Classic rankt, andere 4 geben `rank=None`, Aggregator handled das korrekt |

`asyncio.gather`-Nutzung ist Implementierungs-Detail, kein Behavior — wird nicht direkt getestet (würde nur die Implementation echo'en). Korrektheit der parallelen Fetch wird durch das Standard-asyncio-Verhalten garantiert.

### Regression

Bestehende Tests in `backend/tests/integration/test_runs_endpoint.py` müssen den neuen Constructor-Param mitkriegen — entweder via DI-Update in der Test-Setup oder über `app.dependency_overrides`. Erwartung: 1–3 Test-Files anzupassen, keine Logik-Änderung.

---

## Risiken & Mitigation

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| Bestehende Service-Tests brechen wegen neuem Constructor-Param | Hoch | DI-Anpassung in Test-Setup; falls nötig eigener Cleanup-Commit |
| `pd.Timestamp.now(tz="UTC")` macht non-Test-Pfade subtil zeit-abhängig | Mittel | Default in Stub belassen, in Service-Tests immer fixed `end_date` injizieren |
| Performance: 504 Random-Walks à 5 Ticker dauert messbar lange | Niedrig | numpy-vektorisiert; Smoke-Test bei N=500 wenn nötig |
| `asyncio.gather` versteckt Exception-Hierarchie | Niedrig | Standard-Verhalten: erste Exception bubblet, andere werden cancelled — gewünschtes Verhalten |

---

## Definition of Done

- [ ] `MarketDataProvider`-Port und `StubMarketDataProvider`-Adapter committet
- [ ] `RankingRunService` nimmt `market_data_provider`-Constructor-Param entgegen
- [ ] Alle 5 Modelle werden in `create_and_execute_run` ausgeführt
- [ ] `asyncio.gather` für parallelen Fetch
- [ ] Unit-Tests für Stub: 6/6 grün
- [ ] Integration-Test für Multi-Model-Service: ≥3 Tests grün
- [ ] Bestehende `test_runs_endpoint.py` & Co. weiterhin grün
- [ ] mypy strict + ruff check + ruff format clean
- [ ] AI-USAGE.md-Eintrag
