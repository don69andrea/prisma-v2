"""RankingRunService — orchestriert Erstellung und Ausführung von Ranking-Läufen."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.application.services.ranking_aggregator import RankingAggregator
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig
from backend.domain.models.quality_classic import QualityClassicModel
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository


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
    ) -> None:
        self._universe_repo = universe_repo
        self._run_repo = run_repo
        self._fundamentals_provider = fundamentals_provider

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
