"""Integrationstests für POST /api/v1/backtests und GET /api/v1/backtests/{id}."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.application.services.backtest_service import BacktestService
from backend.domain.entities.backtest_result import BacktestResult
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import Universe, WeightConfig
from backend.domain.repositories.backtest_result_repository import BacktestResultRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_backtest_service

pytestmark = pytest.mark.integration

# ── Constants ─────────────────────────────────────────────────────────────

_TICKERS = ["AAPL", "GOOGL", "MSFT"]

_today = date.today()
_STUB_END = pd.Timestamp(date(_today.year, _today.month, _today.day), tz="UTC")
_BACKTEST_START = date(_today.year - 1, 1, 1)
_BACKTEST_END = date(_today.year - 1, 6, 30)

_UNIVERSE_ID = uuid.uuid4()
_RUN_ID = uuid.uuid4()

_UNIVERSE = Universe(
    id=_UNIVERSE_ID,
    name="Backtest-Test-Universe",
    region="US",
    tickers=tuple(_TICKERS),
)
_RUN = RankingRun(
    id=_RUN_ID,
    created_at=datetime.now(tz=UTC),
    universe_id=_UNIVERSE_ID,
    weight_config=WeightConfig.equal(),
    status="completed",
)
_RESULTS = [
    {"ticker": t, "total_rank": i + 1, "is_sweet_spot": False} for i, t in enumerate(_TICKERS)
]


# ── In-memory repos ───────────────────────────────────────────────────────


class _InMemoryBacktestResultRepository(BacktestResultRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, BacktestResult] = {}

    async def save(self, result: BacktestResult) -> None:
        self._store[result.id] = result

    async def get(self, result_id: UUID) -> BacktestResult | None:
        return self._store.get(result_id)


class _InMemoryUniverseRepository(UniverseRepository):
    def __init__(self) -> None:
        self._data: dict[UUID, Universe] = {}

    async def get(self, universe_id: UUID) -> Universe | None:
        return self._data.get(universe_id)

    async def list(self) -> list[Universe]:
        return list(self._data.values())

    async def save(self, universe: Universe) -> None:
        self._data[universe.id] = universe


class _InMemoryRankingRunRepository(RankingRunRepository):
    def __init__(self) -> None:
        self._runs: dict[UUID, RankingRun] = {}
        self._results: dict[UUID, list[dict[str, Any]]] = {}

    async def get(self, run_id: UUID) -> RankingRun | None:
        return self._runs.get(run_id)

    async def save(self, run: RankingRun) -> None:
        self._runs[run.id] = run

    async def list_by_universe(self, universe_id: UUID) -> list[RankingRun]:
        return [r for r in self._runs.values() if r.universe_id == universe_id]

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[RankingRun]:
        return list(self._runs.values())[offset : offset + limit]

    async def save_results(self, run_id: UUID, results: list[dict[str, Any]]) -> None:
        self._results[run_id] = results

    async def get_results(self, run_id: UUID) -> list[dict[str, Any]] | None:
        return self._results.get(run_id)

    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        for results in self._results.values():
            for item in results:
                if item.get("ticker") == ticker.upper():
                    return item
        return None


# ── Fixture ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[AsyncClient, None]:
    universe_repo = _InMemoryUniverseRepository()
    await universe_repo.save(_UNIVERSE)

    run_repo = _InMemoryRankingRunRepository()
    await run_repo.save(_RUN)
    await run_repo.save_results(_RUN_ID, _RESULTS)

    result_repo = _InMemoryBacktestResultRepository()

    service = BacktestService(
        run_repo=run_repo,
        universe_repo=universe_repo,
        market_data=StubMarketDataProvider(end_date=_STUB_END),
        result_repo=result_repo,
    )

    app = create_app()
    app.dependency_overrides[get_backtest_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def _backtest_body(run_id: UUID = _RUN_ID, top_n: int = 2) -> dict[str, Any]:
    return {
        "model_run_id": str(run_id),
        "start_date": str(_BACKTEST_START),
        "end_date": str(_BACKTEST_END),
        "top_n": top_n,
        "benchmark_ticker": "AAPL",
    }


# ── POST /api/v1/backtests ────────────────────────────────────────────────


async def test_post_backtest_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.post("/api/v1/backtests", json=_backtest_body())
    assert response.status_code == 200


async def test_post_backtest_response_has_id_and_run_id(http_client: AsyncClient) -> None:
    response = await http_client.post("/api/v1/backtests", json=_backtest_body())
    body = response.json()
    assert "id" in body
    assert body["model_run_id"] == str(_RUN_ID)


async def test_post_backtest_series_has_data(http_client: AsyncClient) -> None:
    response = await http_client.post("/api/v1/backtests", json=_backtest_body())
    series = response.json()["series"]
    assert len(series["dates"]) > 0
    assert len(series["prisma"]) == len(series["dates"])
    assert len(series["universe"]) == len(series["dates"])
    assert len(series["benchmark"]) == len(series["dates"])


async def test_post_backtest_returns_metrics(http_client: AsyncClient) -> None:
    response = await http_client.post("/api/v1/backtests", json=_backtest_body())
    body = response.json()
    for key in ("prisma_metrics", "universe_metrics", "benchmark_metrics"):
        assert key in body
        for metric in ("total_return", "cagr", "annual_vol", "sharpe", "max_drawdown"):
            assert metric in body[key]


async def test_post_backtest_unknown_run_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.post("/api/v1/backtests", json=_backtest_body(run_id=uuid.uuid4()))
    assert response.status_code == 404


# ── GET /api/v1/backtests/{id} ────────────────────────────────────────────


async def test_get_backtest_result_returns_200(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/backtests", json=_backtest_body())
    result_id = post.json()["id"]
    response = await http_client.get(f"/api/v1/backtests/{result_id}")
    assert response.status_code == 200


async def test_get_backtest_result_matches_post(http_client: AsyncClient) -> None:
    post = await http_client.post("/api/v1/backtests", json=_backtest_body())
    result_id = post.json()["id"]
    get_body = (await http_client.get(f"/api/v1/backtests/{result_id}")).json()
    assert get_body["id"] == result_id
    assert get_body["model_run_id"] == str(_RUN_ID)


async def test_get_backtest_unknown_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.get(f"/api/v1/backtests/{uuid.uuid4()}")
    assert response.status_code == 404
