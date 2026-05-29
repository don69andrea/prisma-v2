"""Integrationstests: universe_name in RunResponse aus Endpoints."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import Universe, WeightConfig
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import (
    get_fundamentals_provider,
    get_market_data_provider,
    get_ranking_run_repository,
    get_universe_repository,
)

pytestmark = pytest.mark.integration


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
        items = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
        return items[offset : offset + limit]

    async def save_results(self, run_id: uuid.UUID, results: list[dict[str, Any]]) -> None:
        self._results[run_id] = results

    async def get_results(self, run_id: uuid.UUID) -> list[dict[str, Any]] | None:
        return self._results.get(run_id)

    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        return None


class StubFundamentals(FundamentalsProvider):
    async def get_fundamentals(self, tickers: list[str]) -> Any:
        return pd.DataFrame()


class StubMarketData(MarketDataProvider):
    async def get_prices(self, tickers: list[str]) -> Any:
        return pd.DataFrame()


@pytest_asyncio.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[
    tuple[AsyncClient, InMemoryUniverseRepository, InMemoryRankingRunRepository], None
]:
    monkeypatch.setenv("PRISMA_API_KEY", "test-key")

    universe_repo = InMemoryUniverseRepository()
    run_repo = InMemoryRankingRunRepository()

    app = create_app()
    app.dependency_overrides[get_universe_repository] = lambda: universe_repo
    app.dependency_overrides[get_ranking_run_repository] = lambda: run_repo
    app.dependency_overrides[get_fundamentals_provider] = lambda: StubFundamentals()
    app.dependency_overrides[get_market_data_provider] = lambda: StubMarketData()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, universe_repo, run_repo


async def _seed_universe_and_run(
    universe_repo: InMemoryUniverseRepository,
    run_repo: InMemoryRankingRunRepository,
    *,
    universe_name: str = "Demo-US-5",
    status: str = "completed",
) -> tuple[uuid.UUID, uuid.UUID]:
    from datetime import UTC, datetime

    universe = Universe(
        id=uuid.uuid4(),
        name=universe_name,
        region="US",
        tickers=("AAPL", "MSFT"),
    )
    await universe_repo.save(universe)

    run = RankingRun(
        id=uuid.uuid4(),
        created_at=datetime.now(tz=UTC),
        universe_id=universe.id,
        weight_config=WeightConfig.equal(),
        status=status,  # type: ignore[arg-type]
    )
    await run_repo.save(run)
    return universe.id, run.id


@pytest.mark.asyncio
async def test_list_runs_returns_universe_name(
    client: tuple[AsyncClient, Any, Any],
) -> None:
    c, urepo, rrepo = client
    _, run_id = await _seed_universe_and_run(urepo, rrepo, universe_name="Demo-US-5")

    response = await c.get("/api/v1/runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["universe_name"] == "Demo-US-5"
    assert payload[0]["id"] == str(run_id)


@pytest.mark.asyncio
async def test_get_run_returns_universe_name(
    client: tuple[AsyncClient, Any, Any],
) -> None:
    c, urepo, rrepo = client
    _, run_id = await _seed_universe_and_run(urepo, rrepo, universe_name="Tech-Big-12")

    response = await c.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["universe_name"] == "Tech-Big-12"


@pytest.mark.asyncio
async def test_get_run_deleted_universe_fallback(
    client: tuple[AsyncClient, Any, Any],
) -> None:
    c, urepo, rrepo = client
    universe_id, run_id = await _seed_universe_and_run(urepo, rrepo)

    # Universe nachträglich löschen
    urepo._data.pop(universe_id)

    response = await c.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["universe_name"] == "(deleted)"


@pytest.mark.asyncio
async def test_list_runs_deleted_universe_fallback(
    client: tuple[AsyncClient, Any, Any],
) -> None:
    c, urepo, rrepo = client
    universe_id, _ = await _seed_universe_and_run(urepo, rrepo)
    urepo._data.pop(universe_id)

    response = await c.get("/api/v1/runs")

    assert response.status_code == 200
    assert response.json()[0]["universe_name"] == "(deleted)"
