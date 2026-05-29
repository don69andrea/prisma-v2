"""Integration-Tests für RankingRunService mit allen 5 Modellen.

Spec: docs/specs/2026-05-09-ranking-service-multi-model.md
"""

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pandas as pd
import pytest
import pytest_asyncio

from backend.application.services.ranking_run_service import RankingRunService
from backend.application.services.stock_service import StockService
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.stock import Stock
from backend.domain.entities.universe import Universe
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
        self._runs: dict[uuid.UUID, RankingRun] = {}
        self._results: dict[uuid.UUID, list[dict[str, Any]]] = {}

    async def save(self, run: RankingRun) -> None:
        self._runs[run.id] = run

    async def get(self, run_id: uuid.UUID) -> RankingRun | None:
        return self._runs.get(run_id)

    async def list_by_universe(self, universe_id: uuid.UUID) -> list[RankingRun]:
        return [r for r in self._runs.values() if r.universe_id == universe_id]

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[RankingRun]:
        return list(self._runs.values())[offset : offset + limit]

    async def save_results(self, run_id: uuid.UUID, results: list[dict[str, Any]]) -> None:
        self._results[run_id] = results

    async def get_results(self, run_id: uuid.UUID) -> list[dict[str, Any]] | None:
        return self._results.get(run_id)

    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        for results in self._results.values():
            for item in results:
                if item.get("ticker") == ticker.upper():
                    return item
        return None


class StubFundamentalsAllGood(FundamentalsProvider):
    async def get_fundamentals(self, tickers: list[str]) -> UniverseData:
        return {
            t: {
                "pe_ratio": 15.0,
                "pb_ratio": 2.0,
                "fcf_yield": 0.05,
                "operating_margin": 0.20,
                "dividend_yield": 0.03,
                "debt_to_equity": 0.5,
                "eps_growth_3y": 0.10,
                "sales_growth_3y": 0.08,
            }
            for t in tickers
        }


class InMemoryStockService(StockService):
    """Test-Double: maps tickers to fixed Stock entities with deterministic UUIDs."""

    # Bekannte Ticker→UUID-Mapping (deterministisch via uuid.uuid5)
    _NS = uuid.UUID("00000000-0000-0000-0000-000000000001")

    def __init__(self, tickers: list[str]) -> None:
        # Kein super().__init__() — kein echtes Repository benötigt
        self._by_ticker: dict[str, Stock] = {
            t.upper(): Stock(
                id=uuid.uuid5(self._NS, t.upper()),
                ticker=t.upper(),
                name=f"Stub {t.upper()}",
                currency="USD",
            )
            for t in tickers
        }

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        return self._by_ticker.get(ticker.upper())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_UNIVERSE_TICKERS = ("AAPL", "MSFT", "GOOGL", "NVDA", "JPM")


@pytest_asyncio.fixture
async def service_setup() -> AsyncGenerator[
    tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID], None
]:
    universe_repo = InMemoryUniverseRepository()
    run_repo = InMemoryRankingRunRepository()
    fundamentals = StubFundamentalsAllGood()
    market_data = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
    stock_service = InMemoryStockService(list(_UNIVERSE_TICKERS))

    universe_id = uuid.uuid4()
    await universe_repo.save(
        Universe(
            id=universe_id,
            name="Test Universe",
            tickers=_UNIVERSE_TICKERS,
            region="US",
        )
    )

    service = RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals,
        market_data_provider=market_data,
        stock_service=stock_service,
    )
    yield service, universe_repo, universe_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_with_all_five_models_produces_per_model_ranks(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """per_model_ranks-Dict enthält Keys für alle 5 Modelle (vorher nur quality_classic)."""
    service, _, universe_id = service_setup
    run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    assert len(rankings) == 5  # 5 Tickers
    expected_models = {
        "quality_classic",
        "diversification",
        "trend_momentum",
        "value_alpha_potential",
        "alpha",
    }
    for entry in rankings:
        assert set(entry["per_model_ranks"].keys()) == expected_models


async def test_run_produces_valid_total_ranks(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """Mit allen 5 Modellen + Stub-Daten: jeder Ticker hat einen total_rank im
    gültigen Bereich [1, 5]. Ties über method="min" sind erlaubt (z.B. [1,2,2,4,5]).
    """
    service, _, universe_id = service_setup
    run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    assert all(r["total_rank"] is not None for r in rankings)
    assert all(1 <= r["total_rank"] <= 5 for r in rankings)
    # Mindestens ein Ticker hat Rang 1 (kanonisches Verhalten von method="min")
    assert any(r["total_rank"] == 1 for r in rankings)


async def test_run_with_empty_prices_falls_back_to_quality_only(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """Wenn MarketDataProvider leer liefert → 4 Preis-Modelle geben rank=None,
    QualityClassic rankt normal. Aggregator handled das korrekt
    (existierendes Behavior — diese 4 Modelle tragen nicht zum weighted_avg bei).
    """
    service, _, universe_id = service_setup

    class EmptyPrices(MarketDataProvider):
        async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
            return pd.DataFrame()

    service._market_data_provider = EmptyPrices()
    run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    qc_ranks = [r["per_model_ranks"]["quality_classic"] for r in rankings]
    assert any(r is not None for r in qc_ranks)

    other_models = ["diversification", "trend_momentum", "value_alpha_potential", "alpha"]
    for entry in rankings:
        for m in other_models:
            assert entry["per_model_ranks"][m] is None


async def test_sweet_spot_triggers_with_five_models(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """Mit 5 deterministischen Random-Walk-Tickers ergibt sich echte Varianz
    zwischen Modellen — mindestens ein Ticker landet in Top-25% von ≥3 Modellen
    (is_sweet_spot=True).
    """
    service, _, universe_id = service_setup
    run = await service.create_and_execute_run(universe_id=universe_id)
    rankings = await service.get_rankings(run.id)
    # StubMarketDataProvider erzeugt pro Ticker deterministischen, unterschiedlichen
    # Random-Walk → echte Rang-Varianz zwischen Modellen → Sweet Spot erreichbar
    assert any(r["is_sweet_spot"] for r in rankings)


async def test_create_and_execute_run_writes_stock_id_in_results(
    service_setup: tuple[RankingRunService, InMemoryUniverseRepository, uuid.UUID],
) -> None:
    """JSONB results müssen pro Ranking-Item die stock_id enthalten (Memo-Drilldown-Vorbereitung)."""
    service, _, universe_id = service_setup
    run = await service.create_and_execute_run(universe_id=universe_id)
    rankings = await service.get_rankings(run.id)
    assert len(rankings) == 5

    aapl_result = next((r for r in rankings if r["ticker"] == "AAPL"), None)
    assert aapl_result is not None
    assert "stock_id" in aapl_result

    # stock_id muss ein valider UUID-String sein (nicht None), da AAPL im Stub bekannt ist
    stock_id = aapl_result["stock_id"]
    assert stock_id is not None
    # Verifiziere dass es ein valider UUID-String ist
    parsed = uuid.UUID(stock_id)
    # Stub verwendet uuid5 mit bekanntem Namespace → deterministisch reproduzierbar
    expected_id = uuid.uuid5(InMemoryStockService._NS, "AAPL")
    assert parsed == expected_id

    # Alle anderen Tickers müssen ebenfalls stock_id haben (alle im Stub bekannt)
    for entry in rankings:
        assert "stock_id" in entry
        assert entry["stock_id"] is not None


# ---------------------------------------------------------------------------
# Partial-catalog fixture (only AAPL + MSFT known)
# ---------------------------------------------------------------------------

_PARTIAL_CATALOG_TICKERS = ("AAPL", "MSFT")
_UNKNOWN_TICKERS = ("GOOGL", "NVDA", "JPM")


@pytest_asyncio.fixture
async def service_setup_partial_catalog() -> AsyncGenerator[
    tuple[RankingRunService, uuid.UUID], None
]:
    """Universe hat alle 5 Ticker, StockService kennt nur AAPL + MSFT."""
    universe_repo = InMemoryUniverseRepository()
    run_repo = InMemoryRankingRunRepository()
    fundamentals = StubFundamentalsAllGood()
    market_data = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
    stock_service = InMemoryStockService(list(_PARTIAL_CATALOG_TICKERS))

    universe_id = uuid.uuid4()
    await universe_repo.save(
        Universe(
            id=universe_id,
            name="Partial Catalog Universe",
            tickers=_UNIVERSE_TICKERS,
            region="US",
        )
    )

    service = RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals,
        market_data_provider=market_data,
        stock_service=stock_service,
    )
    yield service, universe_id


async def test_unknown_tickers_get_none_stock_id(
    service_setup_partial_catalog: tuple[RankingRunService, uuid.UUID],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ticker im Universe aber nicht im StockService → stock_id == None + Warning geloggt."""
    service, universe_id = service_setup_partial_catalog

    with caplog.at_level(
        logging.WARNING, logger="backend.application.services.ranking_run_service"
    ):
        run = await service.create_and_execute_run(universe_id=universe_id)

    rankings = await service.get_rankings(run.id)
    assert len(rankings) == 5

    by_ticker = {r["ticker"]: r for r in rankings}

    # Bekannte Ticker müssen valide UUIDs haben
    for ticker in _PARTIAL_CATALOG_TICKERS:
        entry = by_ticker[ticker]
        assert entry["stock_id"] is not None, f"{ticker} sollte eine stock_id haben"
        parsed = uuid.UUID(entry["stock_id"])
        expected = uuid.uuid5(InMemoryStockService._NS, ticker)
        assert parsed == expected

    # Unbekannte Ticker müssen stock_id == None haben
    for ticker in _UNKNOWN_TICKERS:
        entry = by_ticker[ticker]
        assert entry["stock_id"] is None, f"{ticker} sollte stock_id None haben"

    # Warning muss für jeden unbekannten Ticker geloggt worden sein
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    for ticker in _UNKNOWN_TICKERS:
        assert any(ticker in msg for msg in warning_messages), (
            f"Kein Warning-Log für unbekannten Ticker {ticker}"
        )
