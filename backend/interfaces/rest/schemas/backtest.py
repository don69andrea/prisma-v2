"""Pydantic-Schemas für Backtest-REST-Endpunkte."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from backend.domain.entities.backtest_result import BacktestResult, PortfolioMetrics


class RunBacktestRequest(BaseModel):
    model_run_id: UUID
    start_date: date
    end_date: date
    top_n: int = 3
    benchmark_ticker: str = "^SSMI"
    mode: Literal["quant_only", "quant_ml", "full"] = "full"


class PortfolioMetricsResponse(BaseModel):
    total_return: float
    cagr: float
    annual_vol: float
    sharpe: float
    max_drawdown: float

    @classmethod
    def from_entity(cls, m: PortfolioMetrics) -> "PortfolioMetricsResponse":
        return cls(**m.model_dump())


class BacktestSeriesResponse(BaseModel):
    dates: list[date]
    prisma: list[float]
    universe: list[float]
    benchmark: list[float]


class BacktestResultResponse(BaseModel):
    id: UUID
    model_run_id: UUID
    start_date: date
    end_date: date
    top_n: int
    benchmark_ticker: str
    prisma_metrics: PortfolioMetricsResponse
    universe_metrics: PortfolioMetricsResponse
    benchmark_metrics: PortfolioMetricsResponse
    series: BacktestSeriesResponse

    @classmethod
    def from_entity(cls, r: BacktestResult) -> "BacktestResultResponse":
        return cls(
            id=r.id,
            model_run_id=r.model_run_id,
            start_date=r.start_date,
            end_date=r.end_date,
            top_n=r.top_n,
            benchmark_ticker=r.benchmark_ticker,
            prisma_metrics=PortfolioMetricsResponse.from_entity(r.prisma_metrics),
            universe_metrics=PortfolioMetricsResponse.from_entity(r.universe_metrics),
            benchmark_metrics=PortfolioMetricsResponse.from_entity(r.benchmark_metrics),
            series=BacktestSeriesResponse(
                dates=r.series.dates,
                prisma=[float(x) for x in r.series.prisma],
                universe=[float(x) for x in r.series.universe],
                benchmark=[float(x) for x in r.series.benchmark],
            ),
        )
