"""BacktestService — simuliert Portfolio-Performance gegen Benchmarks."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pandas as pd

from backend.domain.entities.backtest_result import BacktestResult, BacktestSeries, PortfolioMetrics
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.backtest_result_repository import BacktestResultRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository


class RunNotFound(Exception):
    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"RankingRun {run_id} not found")


class NoResultsFound(Exception):
    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"No results for RankingRun {run_id}")


class BacktestService:
    def __init__(
        self,
        run_repo: RankingRunRepository,
        universe_repo: UniverseRepository,
        market_data: MarketDataProvider,
        result_repo: BacktestResultRepository,
    ) -> None:
        self._run_repo = run_repo
        self._universe_repo = universe_repo
        self._market_data = market_data
        self._result_repo = result_repo

    async def run_backtest(
        self,
        *,
        model_run_id: UUID,
        start_date: date,
        end_date: date,
        top_n: int,
        benchmark_ticker: str,
    ) -> BacktestResult:
        # 1. Load run
        run = await self._run_repo.get(model_run_id)
        if run is None:
            raise RunNotFound(model_run_id)

        # 2. Get rankings — list of dicts with "ticker" and "total_rank" keys
        raw_results: list[dict[str, Any]] | None = await self._run_repo.get_results(model_run_id)
        if not raw_results:
            raise NoResultsFound(model_run_id)

        sorted_results = sorted(raw_results, key=lambda r: r["total_rank"])
        top_n_tickers = [r["ticker"] for r in sorted_results[:top_n]]

        # 3. Get universe for equal-weight comparison portfolio
        universe = await self._universe_repo.get(run.universe_id)
        all_tickers = list(universe.tickers) if universe else top_n_tickers

        # 4. Fetch market data — get_prices returns last 504 days (no date params)
        needed = list({*top_n_tickers, *all_tickers, benchmark_ticker})
        prices_full = await self._market_data.get_prices(needed)

        # 5. Filter by date range
        start_ts = pd.Timestamp(start_date, tz="UTC")
        end_ts = pd.Timestamp(end_date, tz="UTC")
        prices = prices_full.loc[start_ts:end_ts]

        if prices.empty:
            # Fallback: use the full dataset if date range produces no overlap
            prices = prices_full

        # 6. Simulate 3 portfolios
        prisma_series = self._simulate_portfolio(prices, top_n_tickers)
        universe_series = self._simulate_portfolio(prices, all_tickers)
        benchmark_series = self._simulate_portfolio(prices, [benchmark_ticker])

        # 7. Build dates list (shared index)
        dates = [ts.date() for ts in prisma_series.index]

        # 8. Build result
        result = BacktestResult(
            id=uuid4(),
            model_run_id=model_run_id,
            start_date=start_date,
            end_date=end_date,
            top_n=top_n,
            benchmark_ticker=benchmark_ticker,
            prisma_metrics=self._compute_metrics(prisma_series),
            universe_metrics=self._compute_metrics(universe_series),
            benchmark_metrics=self._compute_metrics(benchmark_series),
            series=BacktestSeries(
                dates=dates,
                prisma=[Decimal(str(round(v, 6))) for v in prisma_series.tolist()],
                universe=[Decimal(str(round(v, 6))) for v in universe_series.tolist()],
                benchmark=[Decimal(str(round(v, 6))) for v in benchmark_series.tolist()],
            ),
            created_at=datetime.now(tz=UTC),
        )

        await self._result_repo.save(result)
        return result

    async def get_backtest_result(self, result_id: UUID) -> BacktestResult | None:
        return await self._result_repo.get(result_id)

    @staticmethod
    def _monthly_rebalance_dates(idx: pd.DatetimeIndex) -> set[pd.Timestamp]:
        """Letzter Trading-Day jedes Kalendermonats im Index.

        Deterministisch aus dem Index abgeleitet — keine Holiday-Calendar-Annahmen.
        Implementation per ``pd.Grouper(freq="ME")``. Bei einem partiellen Monat
        liefert ``last()`` den letzten verfuegbaren Tag im Index.
        Spec: docs/specs/2026-05-12-backtest-service-light.md §5.
        """
        if len(idx) == 0:
            return set()
        grouped = pd.Series(idx, index=idx).groupby(pd.Grouper(freq="ME"))
        return set(grouped.last().dropna())

    @staticmethod
    def _simulate_portfolio(prices: pd.DataFrame, tickers: list[str]) -> pd.Series:
        """Equal-weight portfolio mit Drift + monatlichem Reset auf 1/N.

        Spec: docs/specs/2026-05-12-backtest-service-light.md §5.

        Algorithmus:
        - Start: alle verfuegbaren Ticker mit Gewicht 1/N
        - Pro Trading-Day: Portfolio-Return = sum(weights * returns)
        - Drift: Gewichte werden mit (1 + return) skaliert und renormalisiert
        - Reset: am letzten Trading-Day jedes Kalendermonats zurueck auf 1/N

        Edge-Cases:
        - Late-Listing (Spec §5): Light-Variante nimmt statisches Universum
          ueber die ganze Periode an. Look-Ahead-Bias bewusst akzeptiert.
        - Delisting: ``ffill()`` vor ``pct_change()`` (Approximation, OK fuer MVP).
        - <1 voller Monat: kein Reset, reine Drift.
        - Keine verfuegbaren Ticker: flache 1.0-Serie.
        """
        available = [t for t in tickers if t in prices.columns]
        if not available:
            return pd.Series([1.0] * len(prices), index=prices.index)

        sub = prices[available].ffill()
        returns = sub.pct_change().fillna(0.0)
        n = len(available)
        rebalance_dates = BacktestService._monthly_rebalance_dates(prices.index)

        weights = np.full(n, 1.0 / n)
        portfolio_returns: list[float] = []

        for ts in prices.index:
            day_returns = returns.loc[ts].to_numpy(dtype=float)
            daily_ret = float((weights * day_returns).sum())
            portfolio_returns.append(daily_ret)

            # Drift: Gewichte um Tagesperformance verschieben + renormalisieren
            weights = weights * (1.0 + day_returns)
            total = weights.sum()
            weights = weights / total if total > 0 else np.full(n, 1.0 / n)

            # Monatlicher Reset auf 1/N am letzten Trading-Day des Monats
            if ts in rebalance_dates:
                weights = np.full(n, 1.0 / n)

        return (1.0 + pd.Series(portfolio_returns, index=prices.index)).cumprod()

    @staticmethod
    def _compute_metrics(portfolio: pd.Series) -> PortfolioMetrics:
        """Berechnet 5 Kennzahlen für eine Cumulative-Return-Serie."""
        if len(portfolio) < 2:
            zero = Decimal("0")
            return PortfolioMetrics(
                total_return=zero, cagr=zero, annual_vol=zero, sharpe=zero, max_drawdown=zero
            )

        total_return = float(portfolio.iloc[-1] / portfolio.iloc[0] - 1)
        n_years = len(portfolio) / 252.0
        cagr = (1 + total_return) ** (1.0 / n_years) - 1 if n_years > 0 else 0.0

        daily_returns = portfolio.pct_change().dropna()
        annual_vol = float(daily_returns.std() * math.sqrt(252)) if len(daily_returns) > 1 else 0.0
        sharpe = cagr / annual_vol if annual_vol > 0 else 0.0

        rolling_max = portfolio.cummax()
        max_drawdown = float(
            ((rolling_max - portfolio) / rolling_max.replace(0, float("nan"))).max()
        )

        return PortfolioMetrics(
            total_return=Decimal(str(round(total_return, 6))),
            cagr=Decimal(str(round(cagr, 6))),
            annual_vol=Decimal(str(round(annual_vol, 6))),
            sharpe=Decimal(str(round(sharpe, 6))),
            max_drawdown=Decimal(str(round(max_drawdown, 6))),
        )
