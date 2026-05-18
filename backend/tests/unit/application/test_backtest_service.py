"""Unit-Tests für BacktestService."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.application.services.backtest_service import (
    BacktestService,
    NoResultsFound,
    RunNotFound,
)
from backend.domain.entities.backtest_result import BacktestResult
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import Universe, WeightConfig
from backend.domain.repositories.backtest_result_repository import BacktestResultRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider

pytestmark = pytest.mark.unit


# ── In-memory fake repository ──────────────────────────────────────────────


class InMemoryBacktestResultRepository(BacktestResultRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, BacktestResult] = {}

    async def save(self, result: BacktestResult) -> None:
        self._store[result.id] = result

    async def get(self, result_id: UUID) -> BacktestResult | None:
        return self._store.get(result_id)


# ── Fixtures ──────────────────────────────────────────────────────────────

TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
RUN_ID = uuid4()
UNIVERSE_ID = uuid4()


@pytest.fixture
def fake_run() -> RankingRun:
    return RankingRun(
        id=RUN_ID,
        created_at=datetime.now(tz=UTC),
        universe_id=UNIVERSE_ID,
        weight_config=WeightConfig.equal(),
        status="completed",
    )


@pytest.fixture
def fake_universe() -> Universe:
    return Universe(
        id=UNIVERSE_ID,
        name="Test",
        tickers=tuple(TICKERS),
        region="US",
    )


@pytest.fixture
def fake_results() -> list[dict[str, Any]]:
    return [
        {"ticker": t, "total_rank": i + 1, "is_sweet_spot": False} for i, t in enumerate(TICKERS)
    ]


@pytest.fixture
def service(
    fake_run: RankingRun, fake_universe: Universe, fake_results: list[dict[str, Any]]
) -> BacktestService:
    run_repo = AsyncMock(spec=RankingRunRepository)
    run_repo.get.return_value = fake_run
    run_repo.get_results.return_value = fake_results

    universe_repo = AsyncMock(spec=UniverseRepository)
    universe_repo.get.return_value = fake_universe

    return BacktestService(
        run_repo=run_repo,
        universe_repo=universe_repo,
        market_data=StubMarketDataProvider(),
        result_repo=InMemoryBacktestResultRepository(),
    )


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_backtest_returns_result(service: BacktestService) -> None:
    result = await service.run_backtest(
        model_run_id=RUN_ID,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        top_n=3,
        benchmark_ticker="AAPL",
    )
    assert isinstance(result, BacktestResult)
    assert result.model_run_id == RUN_ID
    assert result.top_n == 3


@pytest.mark.asyncio
async def test_series_has_data_points(service: BacktestService) -> None:
    result = await service.run_backtest(
        model_run_id=RUN_ID,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        top_n=3,
        benchmark_ticker="AAPL",
    )
    assert len(result.series.dates) > 0
    assert len(result.series.prisma) == len(result.series.dates)
    assert len(result.series.universe) == len(result.series.dates)
    assert len(result.series.benchmark) == len(result.series.dates)


@pytest.mark.asyncio
async def test_metrics_are_non_trivial(service: BacktestService) -> None:
    result = await service.run_backtest(
        model_run_id=RUN_ID,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        top_n=3,
        benchmark_ticker="AAPL",
    )
    # Stub data has volatility — annual_vol must be non-zero
    assert result.prisma_metrics.annual_vol > Decimal("0")
    assert result.benchmark_metrics.annual_vol > Decimal("0")


@pytest.mark.asyncio
async def test_result_is_persisted(service: BacktestService) -> None:
    result = await service.run_backtest(
        model_run_id=RUN_ID,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        top_n=3,
        benchmark_ticker="AAPL",
    )
    fetched = await service.get_backtest_result(result.id)
    assert fetched is not None
    assert fetched.id == result.id


@pytest.mark.asyncio
async def test_run_not_found_raises(service: BacktestService) -> None:
    service._run_repo.get.return_value = None  # type: ignore[attr-defined]
    with pytest.raises(RunNotFound):
        await service.run_backtest(
            model_run_id=uuid4(),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            top_n=3,
            benchmark_ticker="AAPL",
        )


@pytest.mark.asyncio
async def test_no_results_raises(service: BacktestService) -> None:
    service._run_repo.get_results.return_value = None  # type: ignore[attr-defined]
    with pytest.raises(NoResultsFound):
        await service.run_backtest(
            model_run_id=RUN_ID,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            top_n=3,
            benchmark_ticker="AAPL",
        )
