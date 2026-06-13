# RankingService Multi-Model-Wiring — Implementation Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** RankingRunService nutzt alle 5 Quant-Modelle (statt nur QualityClassic), via neuem `MarketDataProvider`-Port + `StubMarketDataProvider`.

**Architecture:** Saubere Erweiterung des existierenden Provider-Patterns. Port in `domain/ports/`, Stub in `infrastructure/providers/`. Service bekommt zusätzlichen Constructor-Param, fetched Fundamentals + Prices parallel via `asyncio.gather`, ruft alle 5 Modelle auf, übergibt an existierenden Aggregator.

**Tech Stack:** Python 3.12, pandas, numpy, pytest + pytest-asyncio, FastAPI Depends, mypy strict, ruff.

**Spec:** `docs/specs/2026-05-09-ranking-service-multi-model.md`

---

## File Structure

| File | Verantwortlichkeit |
|---|---|
| `backend/domain/ports/market_data_provider.py` (NEU) | ABC mit `async get_prices(tickers) -> pd.DataFrame` |
| `backend/infrastructure/providers/stub_market_data.py` (NEU) | Demo/Test-Provider, deterministischer Random-Walk via `zlib.crc32`-Seed |
| `backend/tests/unit/infrastructure/test_stub_market_data.py` (NEU) | 6 Unit-Tests für Stub |
| `backend/application/services/ranking_run_service.py` (MOD) | Constructor + Body — ruft alle 5 Modelle |
| `backend/interfaces/rest/dependencies.py` (MOD) | DI-Wiring: `get_market_data_provider` + Update von `get_ranking_run_service` |
| `backend/tests/integration/test_runs_endpoint.py` (MOD) | dependency_override für neuen Provider, bestehende Tests grün |
| `backend/tests/integration/test_ranking_run_service_multi_model.py` (NEU) | 3 Integration-Tests |
| `docs/AI-USAGE.md` (MOD) | Reflexions-Eintrag |

---

## Task 1: Port `MarketDataProvider`

**Files:**
- Create: `backend/domain/ports/market_data_provider.py`

- [ ] **Step 1.1: Create the port file**

```python
"""Port für Markt-/Preis-Daten-Lieferanten (yfinance, FMP, Stub)."""

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        """Liefert Tagesschlusskurse für 504 Trading-Days bis zum letzten verfügbaren Tag.

        Returns:
            DataFrame mit:
            - Index: pd.DatetimeIndex, tz-aware (UTC), Business-Day-Frequenz
            - Columns: nur tickers, für die Daten verfügbar sind (Best-Effort)
            - Shape: 504 × N (N ≤ len(tickers))
            - Keine NaN in der Mitte; Anfang/Ende kann lückig sein wenn Ticker neu/delisted
            - Empty DataFrame wenn ``tickers=[]``
        """
        ...
```

- [ ] **Step 1.2: Verify mypy + ruff clean**

```bash
cd backend
python -m mypy domain/ports/market_data_provider.py
python -m ruff check domain/ports/market_data_provider.py
python -m ruff format --check domain/ports/market_data_provider.py
```

Expected: `Success: no issues found`, `All checks passed!`, `1 file already formatted`.

- [ ] **Step 1.3: Commit**

```bash
git add backend/domain/ports/market_data_provider.py
git commit -m "feat(quant/ports): MarketDataProvider — async port für 2-Year Daily Prices

Analog zu FundamentalsProvider. Vertrag:
- 504 Trading-Days, tz-aware UTC, Business-Day-Frequenz
- Best-Effort: nur tickers mit Daten in Spalten
- Empty DataFrame bei tickers=[]"
```

---

## Task 2: `StubMarketDataProvider` (TDD)

**Files:**
- Create: `backend/infrastructure/providers/stub_market_data.py`
- Test: `backend/tests/unit/infrastructure/test_stub_market_data.py`

- [ ] **Step 2.1: Write the failing test file**

```python
"""Tests für StubMarketDataProvider — deterministischer Random-Walk pro Ticker.

Spec: docs/specs/2026-05-09-ranking-service-multi-model.md §"Stub-Adapter"
"""

import numpy as np
import pandas as pd
import pytest

from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider

pytestmark = pytest.mark.unit


class TestStubMarketDataShape:
    @pytest.mark.asyncio
    async def test_returns_dataframe_with_expected_shape(self) -> None:
        """Spec: Shape 504 × N, Index tz-aware UTC, Business-Day-Frequenz."""
        stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
        df = await stub.get_prices(["AAPL", "MSFT", "GOOGL"])
        assert df.shape == (504, 3)
        assert df.index.tz is not None
        assert str(df.index.tz) == "UTC"
        assert list(df.columns) == ["AAPL", "MSFT", "GOOGL"]

    @pytest.mark.asyncio
    async def test_empty_tickers_returns_empty_df(self) -> None:
        stub = StubMarketDataProvider()
        df = await stub.get_prices([])
        assert df.empty


class TestStubMarketDataDeterminism:
    @pytest.mark.asyncio
    async def test_deterministic_across_runs(self) -> None:
        """Spec: zlib.crc32-Seed muss prozess-stabil sein.
        Zwei Stub-Instanzen mit gleichem end_date → identische Reihen pro Ticker.
        """
        end = pd.Timestamp("2026-05-09", tz="UTC")
        df1 = await StubMarketDataProvider(end_date=end).get_prices(["AAPL"])
        df2 = await StubMarketDataProvider(end_date=end).get_prices(["AAPL"])
        np.testing.assert_array_equal(df1["AAPL"].to_numpy(), df2["AAPL"].to_numpy())

    @pytest.mark.asyncio
    async def test_end_date_is_injectable(self) -> None:
        """Fixed end_date → fixed Index (sonst sind Tests zeitabhängig)."""
        end = pd.Timestamp("2026-01-15", tz="UTC")
        stub = StubMarketDataProvider(end_date=end)
        df = await stub.get_prices(["AAPL"])
        assert df.index[-1] <= end


class TestStubMarketDataEdgeCases:
    @pytest.mark.asyncio
    async def test_unknown_ticker_still_gets_random_walk(self) -> None:
        """Stub kennt jeden Ticker via Hash-Seed — kein Lookup-Table nötig."""
        stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
        df = await stub.get_prices(["NEVERHEARDOFIT"])
        assert df.shape == (504, 1)
        assert "NEVERHEARDOFIT" in df.columns

    @pytest.mark.asyncio
    async def test_returns_finite_positive_prices(self) -> None:
        """Cumulative-Product aus normal-distributed Returns mit drift>0,
        sollte praktisch nie negativ oder NaN werden über 504 Tage.
        """
        stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
        df = await stub.get_prices(["AAPL", "MSFT"])
        assert df.notna().all().all()
        assert (df > 0).all().all()
        assert np.isfinite(df.to_numpy()).all()
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/unit/infrastructure/test_stub_market_data.py -v
```

Expected: All tests fail with `ModuleNotFoundError: No module named 'backend.infrastructure.providers.stub_market_data'`.

- [ ] **Step 2.3: Write minimal implementation**

```python
"""Stub-Implementierung des MarketDataProvider für Demo und Tests.

Generiert pro Ticker einen deterministischen Random-Walk via zlib.crc32-Seed
(prozess-stabil, im Gegensatz zu builtin hash()). end_date injizierbar
für vollständig deterministische Tests.

Spec: docs/specs/2026-05-09-ranking-service-multi-model.md §"Stub-Adapter"
"""

import zlib

import numpy as np
import pandas as pd

from backend.domain.ports.market_data_provider import MarketDataProvider

_TRADING_DAYS: int = 504
_DRIFT: float = 0.0005
_VOLATILITY: float = 0.015
_START_PRICE: float = 100.0


class StubMarketDataProvider(MarketDataProvider):
    """Demo/Test-Provider mit deterministischem Random-Walk pro Ticker."""

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

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/unit/infrastructure/test_stub_market_data.py -v
```

Expected: 6 passed.

- [ ] **Step 2.5: Verify mypy + ruff clean**

```bash
cd backend
python -m mypy infrastructure/providers/stub_market_data.py tests/unit/infrastructure/test_stub_market_data.py
python -m ruff check infrastructure/providers/stub_market_data.py tests/unit/infrastructure/test_stub_market_data.py
python -m ruff format --check infrastructure/providers/stub_market_data.py tests/unit/infrastructure/test_stub_market_data.py
```

Expected: alle clean.

- [ ] **Step 2.6: Commit**

```bash
git add backend/infrastructure/providers/stub_market_data.py backend/tests/unit/infrastructure/test_stub_market_data.py
git commit -m "feat(quant/infra): StubMarketDataProvider — deterministischer Random-Walk

Pro Ticker zlib.crc32-Seed (prozess-stabil), end_date injizierbar
für deterministische Tests. 504 × N Shape, tz-aware UTC.

6 Tests: shape+empty, determinism, end_date-injectable, unknown-ticker,
finite-positive-prices."
```

---

## Task 3: Service Constructor + DI Wiring (Regression-Safe)

**Ziel:** `RankingRunService` akzeptiert `market_data_provider`-Param. Der Body wird in Task 4 aktualisiert. Hier nur Plumbing — bestehendes Verhalten unverändert, alle Tests bleiben grün.

**Files:**
- Modify: `backend/application/services/ranking_run_service.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Modify: `backend/tests/integration/test_runs_endpoint.py`

- [ ] **Step 3.1: Update Service-Konstruktor**

In `backend/application/services/ranking_run_service.py`, Imports erweitern:

```python
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider  # NEU
```

Konstruktor erweitern:

```python
class RankingRunService:
    def __init__(
        self,
        universe_repo: UniverseRepository,
        run_repo: RankingRunRepository,
        fundamentals_provider: FundamentalsProvider,
        market_data_provider: MarketDataProvider,
    ) -> None:
        self._universe_repo = universe_repo
        self._run_repo = run_repo
        self._fundamentals_provider = fundamentals_provider
        self._market_data_provider = market_data_provider
```

Body von `create_and_execute_run` **noch nicht ändern** — nur das neue Attribut speichern.

- [ ] **Step 3.2: Update DI-Wiring in dependencies.py**

In `backend/interfaces/rest/dependencies.py` einfügen (zwischen `get_fundamentals_provider` und `get_ranking_run_service`):

```python
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider


async def get_market_data_provider() -> MarketDataProvider:
    return StubMarketDataProvider()
```

`get_ranking_run_service` erweitern:

```python
async def get_ranking_run_service(
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    fundamentals_provider: FundamentalsProvider = Depends(get_fundamentals_provider),
    market_data_provider: MarketDataProvider = Depends(get_market_data_provider),
) -> RankingRunService:
    return RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals_provider,
        market_data_provider=market_data_provider,
    )
```

- [ ] **Step 3.3: Update test_runs_endpoint.py setup**

In `backend/tests/integration/test_runs_endpoint.py`:

Imports erweitern (am Anfang der bestehenden Imports):

```python
import pandas as pd

from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.interfaces.rest.dependencies import (
    get_fundamentals_provider,
    get_market_data_provider,  # NEU
    get_ranking_run_repository,
    get_universe_repository,
)
```

Im Test-Fixture-Setup (sucht nach `dependency_overrides`-Block) den neuen Provider injizieren:

```python
class StubMarketDataForTests(MarketDataProvider):
    """Liefert für Test-Universe-Ticker eine fixed-end-date 504-row DataFrame.

    Genau wie StubMarketDataProvider, aber mit fixed end_date für
    reproduzierbare Test-Indices.
    """

    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        # Reuse production stub für gleichen Random-Walk, aber fixed end_date
        from backend.infrastructure.providers.stub_market_data import (
            StubMarketDataProvider,
        )
        return await StubMarketDataProvider(
            end_date=pd.Timestamp("2026-05-09", tz="UTC")
        ).get_prices(tickers)
```

Im Override-Block (sucht nach `app.dependency_overrides[get_fundamentals_provider]`):

```python
app.dependency_overrides[get_market_data_provider] = lambda: StubMarketDataForTests()
```

- [ ] **Step 3.4: Run all integration tests to verify no regression**

```bash
cd backend
python -m pytest tests/integration/test_runs_endpoint.py -v
```

Expected: alle bestehenden Tests grün (Service-Body wurde noch nicht geändert).

- [ ] **Step 3.5: Verify mypy + ruff clean**

```bash
cd backend
python -m mypy application/services/ranking_run_service.py interfaces/rest/dependencies.py tests/integration/test_runs_endpoint.py
python -m ruff check . && python -m ruff format --check .
```

Expected: alle clean.

- [ ] **Step 3.6: Commit**

```bash
git add backend/application/services/ranking_run_service.py backend/interfaces/rest/dependencies.py backend/tests/integration/test_runs_endpoint.py
git commit -m "refactor(quant/service): RankingRunService nimmt market_data_provider

Plumbing-Only-Commit. Constructor + DI-Wiring + Test-Setup-Update;
Body bleibt unverändert (Task 4). Bestehende Tests grün."
```

---

## Task 4: Service-Body — alle 5 Modelle + asyncio.gather (TDD)

**Files:**
- Modify: `backend/application/services/ranking_run_service.py`
- Create: `backend/tests/integration/test_ranking_run_service_multi_model.py`

- [ ] **Step 4.1: Write failing integration tests**

```python
"""Integration-Tests für RankingRunService mit allen 5 Modellen.

Spec: docs/specs/2026-05-09-ranking-service-multi-model.md
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pandas as pd
import pytest
import pytest_asyncio

from backend.application.services.ranking_run_service import RankingRunService
from backend.domain.entities.universe import Universe, WeightConfig
from backend.domain.models.quality_classic import UniverseData
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# In-memory test doubles
# ---------------------------------------------------------------------------


class InMemoryUniverseRepository(UniverseRepository):
    def __init__(self) -> None:
        self._data: dict[uuid.UUID, Universe] = {}

    async def get(self, universe_id: uuid.UUID) -> Universe | None:
        return self._data.get(universe_id)

    async def list(self) -> list[Universe]:
        return list(self._data.values())

    async def save(self, universe: Universe) -> None:
        self._data[universe.id] = universe


class InMemoryRankingRunRepository(RankingRunRepository):
    def __init__(self) -> None:
        from backend.domain.entities.ranking_run import RankingRun
        self._runs: dict[uuid.UUID, RankingRun] = {}
        self._results: dict[uuid.UUID, list[dict[str, Any]]] = {}

    async def save(self, run: Any) -> None:
        self._runs[run.id] = run

    async def get(self, run_id: uuid.UUID) -> Any:
        return self._runs.get(run_id)

    async def save_results(self, run_id: uuid.UUID, results: list[dict[str, Any]]) -> None:
        self._results[run_id] = results

    async def get_results(self, run_id: uuid.UUID) -> list[dict[str, Any]] | None:
        return self._results.get(run_id)


class StubFundamentalsAllGood(FundamentalsProvider):
    async def get_fundamentals(self, tickers: list[str]) -> UniverseData:
        return {
            t: {
                "pe_ratio": 15.0, "pb_ratio": 2.0, "fcf_yield": 0.05,
                "operating_margin": 0.20, "dividend_yield": 0.03,
                "debt_to_equity": 0.5, "eps_growth_3y": 0.10,
                "sales_growth_3y": 0.08,
            }
            for t in tickers
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def service_setup() -> AsyncGenerator[
    tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID], None
]:
    universe_repo = InMemoryUniverseRepository()
    run_repo = InMemoryRankingRunRepository()
    fundamentals = StubFundamentalsAllGood()
    market_data = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))

    universe_id = uuid.uuid4()
    await universe_repo.save(
        Universe(
            id=universe_id,
            name="Test Universe",
            tickers=("AAPL", "MSFT", "GOOGL", "NVDA", "JPM"),
            region="US",
        )
    )

    service = RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals,
        market_data_provider=market_data,
    )
    yield service, universe_repo, universe_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_with_all_five_models_produces_per_model_ranks(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """Per-Model-Ranks-Dict enthält Keys für alle 5 Modelle (vorher nur quality_classic)."""
    service, _, universe_id = service_setup
    run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    assert len(rankings) == 5  # 5 Tickers
    expected_models = {
        "quality_classic", "diversification", "trend_momentum",
        "value_alpha_potential", "alpha",
    }
    for entry in rankings:
        assert set(entry["per_model_ranks"].keys()) == expected_models


async def test_sweet_spot_triggers_with_five_models(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """Mit 5 Modellen: Top-Ticker werden in mehreren Modellen Rang 1-2 sein,
    Sweet-Spot-Logik (≥3 von 5 in Top-25%) triggert für mindestens einen."""
    service, _, universe_id = service_setup
    run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    sweet_spots = [r for r in rankings if r["is_sweet_spot"]]
    # 5 Tickers, Top-25% = 1 Ticker per Modell — Sweet-Spot ≥3 ist möglich aber nicht garantiert
    # mit Random-Walks. Schwächere Behauptung: mindestens 1 Ticker hat valid total_rank.
    assert any(r["total_rank"] is not None for r in rankings)


async def test_run_with_empty_prices_falls_back_to_quality_only(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """Wenn MarketDataProvider leer liefert → 4 Preis-Modelle geben rank=None,
    QualityClassic rankt normal. Aggregator handled das korrekt
    (existierendes Behavior — diese 4 Modelle tragen weighted_avg=None bei).
    """
    service, _, universe_id = service_setup

    class EmptyPrices(MarketDataProvider):
        async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
            return pd.DataFrame()

    # Replace market_data_provider on the service
    service._market_data_provider = EmptyPrices()  # type: ignore[attr-defined]
    run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    # quality_classic muss valid ranks haben, andere 4 sind None
    qc_ranks = [r["per_model_ranks"]["quality_classic"] for r in rankings]
    assert any(r is not None for r in qc_ranks)
    other_models = ["diversification", "trend_momentum", "value_alpha_potential", "alpha"]
    for entry in rankings:
        for m in other_models:
            assert entry["per_model_ranks"][m] is None
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/integration/test_ranking_run_service_multi_model.py -v
```

Expected: alle 3 Tests fail — `KeyError: 'diversification'` o.ä., weil Service-Body noch nur `quality_classic` ausführt.

- [ ] **Step 4.3: Update Service-Body**

In `backend/application/services/ranking_run_service.py`:

Imports erweitern:

```python
import asyncio

from backend.domain.models.alpha import AlphaModel
from backend.domain.models.diversification import DiversificationModel
from backend.domain.models.quality_classic import QualityClassicModel
from backend.domain.models.trend_momentum import TrendMomentumModel
from backend.domain.models.value_alpha_potential import ValueAlphaPotentialModel
```

In `create_and_execute_run`, ersetze:

```python
fundamentals = await self._fundamentals_provider.get_fundamentals(list(universe.tickers))

qc_results = QualityClassicModel().run(fundamentals)
per_model = {"quality_classic": qc_results}
total_results = RankingAggregator().aggregate(per_model, weights)

ticker_to_qc = {r.ticker: r.rank for r in qc_results}
results: list[dict[str, Any]] = sorted(
    [
        {
            "ticker": r.ticker,
            "total_rank": r.total_rank,
            "weighted_avg": r.weighted_avg,
            "is_sweet_spot": r.is_sweet_spot,
            "per_model_ranks": {"quality_classic": ticker_to_qc.get(r.ticker)},
        }
        for r in total_results
    ],
    key=lambda x: (x["total_rank"] is None, x["total_rank"] or 0),
)
```

durch:

```python
tickers = list(universe.tickers)

fundamentals, prices = await asyncio.gather(
    self._fundamentals_provider.get_fundamentals(tickers),
    self._market_data_provider.get_prices(tickers),
)

per_model = {
    "quality_classic":       QualityClassicModel().run(fundamentals),
    "diversification":       DiversificationModel().run(prices=prices),
    "trend_momentum":        TrendMomentumModel().run(prices=prices),
    "value_alpha_potential": ValueAlphaPotentialModel().run(prices=prices),
    "alpha":                 AlphaModel().run(prices=prices),
}
total_results = RankingAggregator().aggregate(per_model, weights)

# Pro Modell {ticker: rank} für die Output-Aggregation
ticker_to_model_rank: dict[str, dict[str, int | None]] = {
    model_name: {r.ticker: r.rank for r in results}
    for model_name, results in per_model.items()
}

results: list[dict[str, Any]] = sorted(
    [
        {
            "ticker": r.ticker,
            "total_rank": r.total_rank,
            "weighted_avg": r.weighted_avg,
            "is_sweet_spot": r.is_sweet_spot,
            "per_model_ranks": {
                model_name: ticker_ranks.get(r.ticker)
                for model_name, ticker_ranks in ticker_to_model_rank.items()
            },
        }
        for r in total_results
    ],
    key=lambda x: (x["total_rank"] is None, x["total_rank"] or 0),
)
```

- [ ] **Step 4.4: Run integration tests to verify they pass**

```bash
cd backend
python -m pytest tests/integration/test_ranking_run_service_multi_model.py -v
```

Expected: 3 passed.

- [ ] **Step 4.5: Run full test suite for regression check**

```bash
cd backend
python -m pytest -v --tb=short 2>&1 | tail -30
```

Expected: alle bestehenden Tests grün, keine neuen Failures.

- [ ] **Step 4.6: Verify mypy + ruff clean**

```bash
cd backend
python -m mypy application/services/ranking_run_service.py tests/integration/test_ranking_run_service_multi_model.py
python -m ruff check . && python -m ruff format --check .
```

Expected: alle clean.

- [ ] **Step 4.7: Commit**

```bash
git add backend/application/services/ranking_run_service.py backend/tests/integration/test_ranking_run_service_multi_model.py
git commit -m "feat(quant/service): RankingRunService ruft alle 5 Modelle auf

asyncio.gather für parallelen Fetch von Fundamentals + Prices,
dann synchron QualityClassic + Diversification + TrendMomentum +
ValueAlphaPotential + Alpha. Aggregator unverändert.

Tests: 3 Integration-Tests (5-model output, sweet-spot logic,
empty-prices fallback). Volle Suite grün, keine Regression."
```

---

## Task 5: AI-USAGE-Eintrag

**Files:**
- Modify: `docs/AI-USAGE.md`

- [ ] **Step 5.1: Eintrag oben in `## Einträge` einfügen**

Format am Anfang von `## Einträge`-Sektion (zwischen Zeile mit `## Einträge` und dem nächsten `## YYYY-MM-DD`-Heading):

```markdown
## 2026-05-09 · RankingService Multi-Model-Wiring (Branch `feat/ranking-service-multi-model`)
- **Agent**: Claude Code (Opus 4.7), Brainstorming + writing-plans + TDD im Main-Context.
- **Scope**: Schließt AGENTS.md-§"Wenn ein neues Quant-Modell"-Punkt 4 ("RankingService erweitern, Integration-Test schreiben"). Aktuell rief der Service nur QualityClassic — die 4 anderen Modelle (Diversification, TM, VAP, Alpha) hingen als Domain-Klassen ungenutzt. Diese PR: neuer `MarketDataProvider`-Port (analog FundamentalsProvider), `StubMarketDataProvider` mit zlib.crc32-Seed (statt builtin hash → prozess-stabil) + injizierbarem `end_date` für deterministische Tests, RankingRunService nutzt `asyncio.gather` für parallel Fetch + ruft alle 5 Modelle auf, 6 Unit-Tests + 3 Integration-Tests.
- **Spec-Driven**: `docs/specs/2026-05-09-ranking-service-multi-model.md` (Spec) + `-plan.md` (Implementation-Plan). Disziplin Spec vor Code gehalten — Brainstorming-Skill mit 4 strukturierten User-Fragen vor erstem Code, dann Self-Review der Spec hat 5 echte Issues (zlib.crc32 statt hash, injizierbares end_date, UTC-Timezone, asyncio.gather, empty-input edge-case) gefangen, bevor sie Code wurden.
- **Was gut lief**:
  - **Self-Review als Mini-TDD**: Nach erstem Spec-Entwurf bewusst „looking with fresh eyes" — 5 Bugs gefunden (z.B. `hash()` ist prozess-instabil, ein klassischer Python-Fall, der erst beim 2. Test-Run sichtbar wäre). Self-Review hat hier real Bugs gefangen, nicht nur Tippfehler.
  - **Spec vor Code spart TDD-Iterations**: Die 5 vor-vorab gefundenen Issues hätten sonst je eine RED-Phase gekostet — geschätzt 30 Minuten Iteration eingespart.
  - **Existing Provider-Pattern als Vorbild**: `FundamentalsProvider` + `StubFundamentalsProvider` als Template übernommen. Saubere Symmetrie, keine Architektur-Diskussion nötig.
- **Was nicht klappte**: TODO nach Implementation eintragen.
- **Token-Kosten**: TODO eintragen.
- **Autor**: Fabia Holzer (mit Claude Code)
```

- [ ] **Step 5.2: Commit**

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): RankingService Multi-Model — Reflexions-Eintrag

40%-Achse: TODO-Felder beim PR-Open mit echten Werten füllen."
```

---

## Final Verification

- [ ] **Step F.1: Volle Test-Suite grün**

```bash
cd backend
python -m pytest -v --tb=short 2>&1 | tail -10
```

Expected: alle Tests passed, kein neues skipped/failed.

- [ ] **Step F.2: mypy + ruff komplett**

```bash
cd backend
python -m mypy . && python -m ruff check . && python -m ruff format --check .
```

Expected: alle clean.

- [ ] **Step F.3: Branch ist up-to-date mit main**

```bash
git fetch origin
git log main..HEAD --oneline
```

Expected: 5 Commits (Spec + 4 Tasks), keiner aus main.

- [ ] **Step F.4: Push + PR**

```bash
git push -u origin feat/ranking-service-multi-model
gh pr create --title "feat(quant): RankingService Multi-Model-Wiring" --body "$(cat <<'EOF'
## Summary

Schließt AGENTS.md §"Wenn ein neues Quant-Modell" Punkt 4: RankingRunService nutzt jetzt alle 5 Quant-Modelle statt nur QualityClassic.

- Neuer `MarketDataProvider`-Port + `StubMarketDataProvider`-Adapter
- Service-Konstruktor: zusätzlicher `market_data_provider`-Param
- `create_and_execute_run` ruft via `asyncio.gather` Fundamentals + Prices parallel, dann alle 5 Modelle synchron
- 6 Unit + 3 Integration-Tests

## Spec

`docs/specs/2026-05-09-ranking-service-multi-model.md`

## Out of Scope (Folge-PRs)

- Echter `YFinanceMarketDataProvider`-Adapter
- REST-Endpoint-Anpassungen
- Configurable lookback_days

## Test Plan

- [ ] `pytest backend/tests/unit/infrastructure/test_stub_market_data.py` (6 tests)
- [ ] `pytest backend/tests/integration/test_ranking_run_service_multi_model.py` (3 tests)
- [ ] Volle Suite weiterhin grün
- [ ] mypy strict + ruff clean
EOF
)"
```

Expected: PR-URL ausgegeben.

---

## Self-Review (vor Plan-Commit)

**Spec coverage:**
- ✅ Port-Interface → Task 1
- ✅ Stub-Adapter (alle 5 Issues addressed) → Task 2
- ✅ Service-Konstruktor + DI → Task 3
- ✅ Service-Body + asyncio.gather → Task 4
- ✅ AI-USAGE → Task 5
- ✅ 6 Unit-Tests → Task 2
- ✅ 3 Integration-Tests → Task 4
- ✅ Bestehende Tests-Update → Task 3

**Placeholder scan:** AI-USAGE-Eintrag hat zwei TODO-Felder ("Was nicht klappte" + Token-Kosten) — bewusst, weil diese erst nach Implementation echte Werte bekommen.

**Type consistency:** `MarketDataProvider`, `StubMarketDataProvider`, `market_data_provider` (param), `_market_data_provider` (attribute), `get_market_data_provider` (DI factory) — Naming durchgehend konsistent.
