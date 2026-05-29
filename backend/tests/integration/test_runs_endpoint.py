"""Integrationstests für POST /api/v1/runs, GET /api/v1/runs/{id},
GET /api/v1/runs/{id}/rankings.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §6–7
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import (
    get_fundamentals_provider,
    get_market_data_provider,
    get_ranking_run_repository,
    get_stock_service,
    get_universe_repository,
)


class _InMemoryStockService(StockService):
    """Test-Double — vermeidet DB-backed StockRepository im Integration-Test."""

    _NS = uuid.UUID("00000000-0000-0000-0000-000000000001")

    def __init__(self, tickers: list[str]) -> None:
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


pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# InMemory stubs
# ---------------------------------------------------------------------------

_GOOD: dict[str, float | None] = {
    "pe_ratio": 15.0,
    "pb_ratio": 2.0,
    "fcf_yield": 0.05,
    "operating_margin": 0.20,
    "dividend_yield": 0.03,
    "debt_to_equity": 0.5,
    "eps_growth_3y": 0.10,
    "sales_growth_3y": 0.08,
}


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

    async def get(self, run_id: uuid.UUID) -> RankingRun | None:
        return self._runs.get(run_id)

    async def save(self, run: RankingRun) -> None:
        self._runs[run.id] = run

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


class StubFundamentalsProvider(FundamentalsProvider):
    async def get_fundamentals(self, tickers: list[str]) -> UniverseData:
        return {t: dict(_GOOD) for t in tickers}


class FixedDateStubMarketDataProvider(MarketDataProvider):
    """Wrapper um StubMarketDataProvider mit fixed end_date für reproduzierbare Tests."""

    def __init__(self) -> None:
        self._inner = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))

    async def get_prices(self, tickers: list[str]) -> pd.DataFrame:
        return await self._inner.get_prices(tickers)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEMO_UNIVERSE_ID = uuid.uuid4()
_DEMO_UNIVERSE = Universe(
    id=_DEMO_UNIVERSE_ID,
    name="Test-Universe",
    region="US",
    tickers=("AAPL", "MSFT", "GOOGL"),
)


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[AsyncClient, None]:
    universe_repo = InMemoryUniverseRepository()
    await universe_repo.save(_DEMO_UNIVERSE)

    run_repo = InMemoryRankingRunRepository()
    fundamentals_provider = StubFundamentalsProvider()
    market_data_provider = FixedDateStubMarketDataProvider()

    stock_service = _InMemoryStockService(list(_DEMO_UNIVERSE.tickers))

    app = create_app()
    app.dependency_overrides[get_universe_repository] = lambda: universe_repo
    app.dependency_overrides[get_ranking_run_repository] = lambda: run_repo
    app.dependency_overrides[get_fundamentals_provider] = lambda: fundamentals_provider
    app.dependency_overrides[get_market_data_provider] = lambda: market_data_provider
    app.dependency_overrides[get_stock_service] = lambda: stock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# POST /api/v1/runs
# ---------------------------------------------------------------------------


async def test_post_run_returns_201(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/runs",
        json={"universe_id": str(_DEMO_UNIVERSE_ID)},
    )
    assert response.status_code == 201


async def test_post_run_response_has_id_and_status(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/runs",
        json={"universe_id": str(_DEMO_UNIVERSE_ID)},
    )
    body = response.json()
    assert "id" in body
    assert "status" in body
    assert body["status"] == "completed"


async def test_post_run_unknown_universe_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/runs",
        json={"universe_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


async def test_post_run_invalid_weights_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/runs",
        json={
            "universe_id": str(_DEMO_UNIVERSE_ID),
            "weight_config": {"quality_classic": 0.5},  # sum != 1.0
        },
    )
    assert response.status_code == 422


async def test_post_run_custom_weights_accepted(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/runs",
        json={
            "universe_id": str(_DEMO_UNIVERSE_ID),
            "weight_config": {"quality_classic": 1.0},
        },
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/runs/{id}
# ---------------------------------------------------------------------------


async def test_get_run_returns_200(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    response = await http_client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200


async def test_get_run_returns_correct_fields(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    body = (await http_client.get(f"/api/v1/runs/{run_id}")).json()
    assert body["id"] == run_id
    assert body["status"] == "completed"
    assert body["universe_id"] == str(_DEMO_UNIVERSE_ID)


async def test_get_run_unknown_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.get(f"/api/v1/runs/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/runs/{id}/rankings
# ---------------------------------------------------------------------------


async def test_get_rankings_returns_200(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    response = await http_client.get(f"/api/v1/runs/{run_id}/rankings")
    assert response.status_code == 200


async def test_get_rankings_returns_all_tickers(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    rankings = (await http_client.get(f"/api/v1/runs/{run_id}/rankings")).json()
    tickers = {r["ticker"] for r in rankings}
    assert tickers == {"AAPL", "MSFT", "GOOGL"}


async def test_get_rankings_items_have_expected_fields(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    rankings = (await http_client.get(f"/api/v1/runs/{run_id}/rankings")).json()
    item = rankings[0]
    assert "ticker" in item
    assert "total_rank" in item
    assert "is_sweet_spot" in item
    assert "per_model_ranks" in item


async def test_get_rankings_per_model_ranks_has_all_five_models(
    http_client: AsyncClient,
) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    rankings = (await http_client.get(f"/api/v1/runs/{run_id}/rankings")).json()
    expected_models = {
        "quality_classic",
        "diversification",
        "trend_momentum",
        "value_alpha_potential",
        "alpha",
    }
    for item in rankings:
        assert set(item["per_model_ranks"].keys()) == expected_models


async def test_get_rankings_sorted_by_total_rank(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE_ID)})
    run_id = post.json()["id"]
    rankings = (await http_client.get(f"/api/v1/runs/{run_id}/rankings")).json()
    ranked = [r["total_rank"] for r in rankings if r["total_rank"] is not None]
    assert ranked == sorted(ranked)


async def test_get_rankings_unknown_run_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.get(f"/api/v1/runs/{uuid.uuid4()}/rankings")
    assert response.status_code == 404
