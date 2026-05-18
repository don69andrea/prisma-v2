"""SQLAlchemy-Implementierung des BacktestResultRepository-Ports."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.backtest_result import BacktestResult, BacktestSeries, PortfolioMetrics
from backend.domain.repositories.backtest_result_repository import BacktestResultRepository
from backend.infrastructure.persistence.models.backtest_result import BacktestResultORM


def _metrics_to_dict(m: PortfolioMetrics) -> dict[str, str]:
    return {k: str(v) for k, v in m.model_dump().items()}


def _metrics_from_dict(d: dict[str, Any]) -> PortfolioMetrics:
    return PortfolioMetrics(**{k: Decimal(v) for k, v in d.items()})


def _series_to_dict(s: BacktestSeries) -> dict[str, list[str]]:
    return {
        "dates": [str(d) for d in s.dates],
        "prisma": [str(v) for v in s.prisma],
        "universe": [str(v) for v in s.universe],
        "benchmark": [str(v) for v in s.benchmark],
    }


def _series_from_dict(d: dict[str, Any]) -> BacktestSeries:
    return BacktestSeries(
        dates=[date.fromisoformat(x) for x in d["dates"]],
        prisma=[Decimal(x) for x in d["prisma"]],
        universe=[Decimal(x) for x in d["universe"]],
        benchmark=[Decimal(x) for x in d["benchmark"]],
    )


class SQLABacktestResultRepository(BacktestResultRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, result: BacktestResult) -> None:
        # Flush pending adds before get() — autoflush=False otherwise means
        # session.get() won't find a row staged via add() in the same session.
        await self._session.flush()
        row = await self._session.get(BacktestResultORM, result.id)
        if row is None:
            self._session.add(
                BacktestResultORM(
                    id=result.id,
                    model_run_id=result.model_run_id,
                    start_date=result.start_date,
                    end_date=result.end_date,
                    top_n=result.top_n,
                    benchmark_ticker=result.benchmark_ticker,
                    prisma_metrics=_metrics_to_dict(result.prisma_metrics),
                    universe_metrics=_metrics_to_dict(result.universe_metrics),
                    benchmark_metrics=_metrics_to_dict(result.benchmark_metrics),
                    series=_series_to_dict(result.series),
                    created_at=result.created_at,
                )
            )

    async def get(self, result_id: UUID) -> BacktestResult | None:
        # Flush before get() for the same reason as save().
        await self._session.flush()
        row = await self._session.get(BacktestResultORM, result_id)
        if row is None:
            return None
        return BacktestResult(
            id=row.id,
            model_run_id=row.model_run_id,
            start_date=row.start_date,
            end_date=row.end_date,
            top_n=row.top_n,
            benchmark_ticker=row.benchmark_ticker,
            prisma_metrics=_metrics_from_dict(row.prisma_metrics),
            universe_metrics=_metrics_from_dict(row.universe_metrics),
            benchmark_metrics=_metrics_from_dict(row.benchmark_metrics),
            series=_series_from_dict(row.series),
            created_at=row.created_at,
        )
