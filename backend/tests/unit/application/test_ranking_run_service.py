"""Unit-Tests für RankingRunService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from backend.application.services.ranking_run_service import (
    RankingRunNotFound,
    RankingRunService,
    UniverseNotFound,
)
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.stock import Stock
from backend.domain.entities.universe import Universe, WeightConfig
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository

pytestmark = pytest.mark.unit

_EQUAL_WEIGHTS = WeightConfig.equal()
_NOW = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _make_universe(tickers: tuple[str, ...] = ("NESN", "ABBN", "NOVN")) -> Universe:
    return Universe(
        id=uuid4(),
        name="SMI Core",
        tickers=tickers,
        region="CH",
    )


def _make_run(
    run_id: UUID | None = None,
    universe_id: UUID | None = None,
    status: str = "completed",
) -> RankingRun:
    return RankingRun(
        id=run_id or uuid4(),
        created_at=_NOW,
        universe_id=universe_id or uuid4(),
        weight_config=_EQUAL_WEIGHTS,
        status=status,  # type: ignore[arg-type]
    )


def _make_stock(ticker: str) -> Stock:
    return Stock(
        id=uuid4(),
        ticker=ticker,
        name=f"{ticker} AG",
        currency="CHF",
    )


def _build_service(
    universe: Universe | None = None,
    saved_run: RankingRun | None = None,
    fundamentals: Any = None,
    prices: Any = None,
) -> tuple[RankingRunService, AsyncMock, AsyncMock, MagicMock, MagicMock, MagicMock]:
    mock_universe_repo = AsyncMock(spec=UniverseRepository)
    mock_universe_repo.get.return_value = universe

    mock_run_repo = AsyncMock(spec=RankingRunRepository)
    mock_run_repo.save.return_value = None
    mock_run_repo.save_results.return_value = None
    mock_run_repo.get.return_value = saved_run
    mock_run_repo.list_all.return_value = []

    mock_fundamentals_provider = AsyncMock()
    mock_fundamentals_provider.get_fundamentals.return_value = (
        fundamentals if fundamentals is not None else MagicMock()
    )

    mock_market_data_provider = AsyncMock()
    mock_market_data_provider.get_prices.return_value = (
        prices if prices is not None else MagicMock()
    )

    mock_stock_service = AsyncMock()
    mock_stock_service.get_by_ticker.return_value = None

    svc = RankingRunService(
        universe_repo=mock_universe_repo,
        run_repo=mock_run_repo,
        fundamentals_provider=mock_fundamentals_provider,
        market_data_provider=mock_market_data_provider,
        stock_service=mock_stock_service,
    )
    return svc, mock_universe_repo, mock_run_repo, mock_fundamentals_provider, mock_market_data_provider, mock_stock_service


class TestCreateAndExecuteRun:
    async def test_raises_universe_not_found_when_missing(self) -> None:
        svc, _, _, _, _, _ = _build_service(universe=None)
        unknown_id = uuid4()

        with pytest.raises(UniverseNotFound) as exc_info:
            await svc.create_and_execute_run(unknown_id)

        assert exc_info.value.universe_id == unknown_id

    async def test_initial_run_saved_with_running_status(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)

        saved_runs: list[RankingRun] = []
        mock_run_repo.save.side_effect = lambda run: saved_runs.append(run)

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            await svc.create_and_execute_run(universe.id)

        first_save = saved_runs[0]
        assert first_save.status == "running"
        assert first_save.universe_id == universe.id

    async def test_completed_run_saved_as_last_call(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)

        saved_runs: list[RankingRun] = []
        mock_run_repo.save.side_effect = lambda run: saved_runs.append(run)

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            result = await svc.create_and_execute_run(universe.id)

        assert result.status == "completed"
        last_save = saved_runs[-1]
        assert last_save.status == "completed"

    async def test_returns_completed_ranking_run(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)
        mock_run_repo.save.return_value = None

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            result = await svc.create_and_execute_run(universe.id)

        assert isinstance(result, RankingRun)
        assert result.status == "completed"
        assert result.universe_id == universe.id

    async def test_uses_provided_weight_config(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)

        saved_runs: list[RankingRun] = []
        mock_run_repo.save.side_effect = lambda run: saved_runs.append(run)

        custom_weights = WeightConfig(
            weights={
                "quality_classic": 0.40,
                "alpha": 0.20,
                "trend_momentum": 0.20,
                "value_alpha_potential": 0.10,
                "diversification": 0.10,
            }
        )

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            result = await svc.create_and_execute_run(universe.id, weight_config=custom_weights)

        assert result.weight_config == custom_weights

    async def test_uses_equal_weights_when_none_provided(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)

        saved_runs: list[RankingRun] = []
        mock_run_repo.save.side_effect = lambda run: saved_runs.append(run)

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            result = await svc.create_and_execute_run(universe.id, weight_config=None)

        assert result.weight_config == WeightConfig.equal()

    async def test_results_saved_via_repo(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)
        mock_run_repo.save.return_value = None

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            await svc.create_and_execute_run(universe.id)

        mock_run_repo.save_results.assert_called_once()

    async def test_run_saved_twice_running_then_completed(self) -> None:
        universe = _make_universe(tickers=("NESN",))
        svc, _, mock_run_repo, _, _, _ = _build_service(universe=universe)

        saved_statuses: list[str] = []
        mock_run_repo.save.side_effect = lambda run: saved_statuses.append(run.status)

        with (
            patch("backend.application.services.ranking_run_service.QualityClassicModel") as mock_qc,
            patch("backend.application.services.ranking_run_service.DiversificationModel") as mock_div,
            patch("backend.application.services.ranking_run_service.TrendMomentumModel") as mock_tm,
            patch("backend.application.services.ranking_run_service.ValueAlphaPotentialModel") as mock_vap,
            patch("backend.application.services.ranking_run_service.AlphaModel") as mock_alpha,
            patch("backend.application.services.ranking_run_service.RankingAggregator") as mock_agg,
        ):
            for mock_model in (mock_qc, mock_div, mock_tm, mock_vap, mock_alpha):
                mock_model.return_value.run.return_value = []
            mock_agg.return_value.aggregate.return_value = []

            await svc.create_and_execute_run(universe.id)

        assert saved_statuses == ["running", "completed"]


class TestGetRun:
    async def test_returns_run_when_found(self) -> None:
        run = _make_run(status="completed")
        svc, _, mock_run_repo, _, _, _ = _build_service(saved_run=run)
        mock_run_repo.get.return_value = run

        result = await svc.get_run(run.id)

        assert result is run
        mock_run_repo.get.assert_called_once_with(run.id)

    async def test_raises_ranking_run_not_found_when_missing(self) -> None:
        svc, _, mock_run_repo, _, _, _ = _build_service(saved_run=None)
        missing_id = uuid4()

        with pytest.raises(RankingRunNotFound) as exc_info:
            await svc.get_run(missing_id)

        assert exc_info.value.run_id == missing_id

    async def test_ranking_run_not_found_message_contains_id(self) -> None:
        svc, _, mock_run_repo, _, _, _ = _build_service(saved_run=None)
        missing_id = uuid4()

        with pytest.raises(RankingRunNotFound) as exc_info:
            await svc.get_run(missing_id)

        assert str(missing_id) in str(exc_info.value)


class TestGetRankings:
    async def test_returns_results_list_when_run_exists(self) -> None:
        run = _make_run(status="completed")
        results: list[dict[str, Any]] = [
            {"ticker": "NESN", "total_rank": 1, "weighted_avg": 0.85},
        ]
        svc, _, mock_run_repo, _, _, _ = _build_service(saved_run=run)
        mock_run_repo.get.return_value = run
        mock_run_repo.get_results.return_value = results

        output = await svc.get_rankings(run.id)

        assert output == results
        mock_run_repo.get_results.assert_called_once_with(run.id)

    async def test_raises_ranking_run_not_found_when_run_missing(self) -> None:
        svc, _, mock_run_repo, _, _, _ = _build_service(saved_run=None)
        missing_id = uuid4()

        with pytest.raises(RankingRunNotFound):
            await svc.get_rankings(missing_id)

    async def test_returns_empty_list_when_no_results_stored(self) -> None:
        run = _make_run(status="running")
        svc, _, mock_run_repo, _, _, _ = _build_service(saved_run=run)
        mock_run_repo.get.return_value = run
        mock_run_repo.get_results.return_value = None

        output = await svc.get_rankings(run.id)

        assert output == []


class TestListRuns:
    async def test_delegates_to_repository_with_defaults(self) -> None:
        svc, _, mock_run_repo, _, _, _ = _build_service()
        mock_run_repo.list_all.return_value = []

        await svc.list_runs()

        mock_run_repo.list_all.assert_called_once_with(limit=50, offset=0)

    async def test_passes_custom_limit_and_offset(self) -> None:
        svc, _, mock_run_repo, _, _, _ = _build_service()
        mock_run_repo.list_all.return_value = []

        await svc.list_runs(limit=10, offset=20)

        mock_run_repo.list_all.assert_called_once_with(limit=10, offset=20)

    async def test_returns_list_from_repository(self) -> None:
        run1 = _make_run(status="completed")
        run2 = _make_run(status="completed")
        svc, _, mock_run_repo, _, _, _ = _build_service()
        mock_run_repo.list_all.return_value = [run1, run2]

        result = await svc.list_runs()

        assert result == [run1, run2]

    async def test_returns_empty_list_when_no_runs(self) -> None:
        svc, _, mock_run_repo, _, _, _ = _build_service()
        mock_run_repo.list_all.return_value = []

        result = await svc.list_runs()

        assert result == []
