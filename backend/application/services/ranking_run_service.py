"""RankingRunService — orchestriert Erstellung und Ausführung von Ranking-Läufen."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.application.services.ranking_aggregator import RankingAggregator
from backend.application.services.stock_service import StockService
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig
from backend.domain.models.alpha import AlphaModel
from backend.domain.models.diversification import DiversificationModel
from backend.domain.models.quality_classic import QualityClassicModel
from backend.domain.models.trend_momentum import TrendMomentumModel
from backend.domain.models.value_alpha_potential import ValueAlphaPotentialModel
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository

_logger = logging.getLogger(__name__)


class UniverseNotFound(Exception):
    def __init__(self, universe_id: UUID) -> None:
        super().__init__(f"Universe {universe_id} not found")
        self.universe_id = universe_id


class RankingRunNotFound(Exception):
    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"RankingRun {run_id} not found")
        self.run_id = run_id


class RankingRunService:
    def __init__(
        self,
        universe_repo: UniverseRepository,
        run_repo: RankingRunRepository,
        fundamentals_provider: FundamentalsProvider,
        market_data_provider: MarketDataProvider,
        stock_service: StockService,
    ) -> None:
        self._universe_repo = universe_repo
        self._run_repo = run_repo
        self._fundamentals_provider = fundamentals_provider
        self._market_data_provider = market_data_provider
        self._stock_service = stock_service

    async def create_and_execute_run(
        self,
        universe_id: UUID,
        weight_config: WeightConfig | None = None,
    ) -> RankingRun:
        universe = await self._universe_repo.get(universe_id)
        if universe is None:
            raise UniverseNotFound(universe_id)

        weights = weight_config or WeightConfig.equal()
        run = RankingRun(
            id=uuid4(),
            created_at=datetime.now(tz=UTC),
            universe_id=universe_id,
            weight_config=weights,
            status="running",
        )
        await self._run_repo.save(run)

        tickers = list(universe.tickers)

        fundamentals, prices = await asyncio.gather(
            self._fundamentals_provider.get_fundamentals(tickers),
            self._market_data_provider.get_prices(tickers),
        )

        per_model = {
            "quality_classic": QualityClassicModel().run(fundamentals),
            "diversification": DiversificationModel().run(prices=prices),
            "trend_momentum": TrendMomentumModel().run(prices=prices),
            "value_alpha_potential": ValueAlphaPotentialModel().run(prices=prices),
            "alpha": AlphaModel().run(prices=prices),
        }
        total_results = RankingAggregator().aggregate(per_model, weights)

        ticker_to_model_rank: dict[str, dict[str, int | None]] = {
            model_name: {r.ticker: r.rank for r in results}
            for model_name, results in per_model.items()
        }

        tickers_in_results = [r.ticker for r in total_results]
        stock_id_by_ticker: dict[str, str | None] = {}
        for ticker in tickers_in_results:
            stock = await self._stock_service.get_by_ticker(ticker)
            if stock is None:
                _logger.warning(
                    "stock_id lookup failed for ticker %s in run %s — Memo-Drilldown will be disabled for this row",
                    ticker,
                    run.id,
                )
                stock_id_by_ticker[ticker] = None
            else:
                stock_id_by_ticker[ticker] = str(stock.id)

        results: list[dict[str, Any]] = sorted(
            [
                {
                    "stock_id": stock_id_by_ticker[r.ticker],
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

        await self._run_repo.save_results(run.id, results)

        completed_run = RankingRun(
            id=run.id,
            created_at=run.created_at,
            universe_id=run.universe_id,
            weight_config=run.weight_config,
            status="completed",
        )
        await self._run_repo.save(completed_run)
        return completed_run

    async def get_run(self, run_id: UUID) -> RankingRun:
        run = await self._run_repo.get(run_id)
        if run is None:
            raise RankingRunNotFound(run_id)
        return run

    async def get_rankings(self, run_id: UUID) -> list[dict[str, Any]]:
        run = await self._run_repo.get(run_id)
        if run is None:
            raise RankingRunNotFound(run_id)
        return await self._run_repo.get_results(run_id) or []

    async def list_runs(self, limit: int = 50, offset: int = 0) -> list[RankingRun]:
        return await self._run_repo.list_all(limit=limit, offset=offset)
