"""Unit-Tests für die BacktestResult-Entity."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.domain.entities.backtest_result import (
    BacktestResult,
    BacktestSeries,
    PortfolioMetrics,
)

pytestmark = pytest.mark.unit


def _make_metrics(**overrides: object) -> PortfolioMetrics:
    """Factory für PortfolioMetrics."""
    defaults: dict[str, object] = {
        "total_return": Decimal("0.15"),
        "cagr": Decimal("0.075"),
        "annual_vol": Decimal("0.12"),
        "sharpe": Decimal("0.625"),
        "max_drawdown": Decimal("0.08"),
    }
    defaults.update(overrides)
    return PortfolioMetrics(**defaults)  # type: ignore[arg-type]


def _make_series(**overrides: object) -> BacktestSeries:
    """Factory für BacktestSeries."""
    defaults: dict[str, object] = {
        "dates": [date(2024, 1, 31), date(2024, 2, 29)],
        "prisma": [Decimal("1.0"), Decimal("1.05")],
        "universe": [Decimal("1.0"), Decimal("1.03")],
        "benchmark": [Decimal("1.0"), Decimal("1.02")],
    }
    defaults.update(overrides)
    return BacktestSeries(**defaults)  # type: ignore[arg-type]


def _make_result(**overrides: object) -> BacktestResult:
    """Factory für BacktestResult."""
    metrics = _make_metrics()
    series = _make_series()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "model_run_id": uuid4(),
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 12, 31),
        "actual_start_date": date(2024, 1, 1),
        "actual_end_date": date(2024, 12, 31),
        "top_n": 3,
        "benchmark_ticker": "^SSMI",
        "prisma_metrics": metrics,
        "universe_metrics": metrics,
        "benchmark_metrics": metrics,
        "series": series,
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return BacktestResult(**defaults)  # type: ignore[arg-type]


class TestPortfolioMetrics:
    def test_construction(self) -> None:
        metrics = _make_metrics()
        assert metrics.total_return == Decimal("0.15")
        assert metrics.cagr == Decimal("0.075")
        assert metrics.annual_vol == Decimal("0.12")
        assert metrics.sharpe == Decimal("0.625")
        assert metrics.max_drawdown == Decimal("0.08")

    def test_immutability(self) -> None:
        metrics = _make_metrics()
        with pytest.raises(ValidationError):
            metrics.total_return = Decimal("0.20")


class TestBacktestSeries:
    def test_construction(self) -> None:
        series = _make_series()
        assert len(series.dates) == 2
        assert len(series.prisma) == 2
        assert len(series.universe) == 2
        assert len(series.benchmark) == 2

    def test_lengths_match(self) -> None:
        series = _make_series()
        assert len(series.dates) == len(series.prisma)
        assert len(series.prisma) == len(series.universe)
        assert len(series.universe) == len(series.benchmark)

    def test_immutability(self) -> None:
        series = _make_series()
        with pytest.raises(ValidationError):
            series.dates = [date(2024, 1, 1)]


class TestBacktestResult:
    def test_construction(self) -> None:
        result = _make_result()
        assert result.top_n == 3
        assert result.benchmark_ticker == "^SSMI"
        assert result.start_date == date(2024, 1, 1)
        assert result.end_date == date(2024, 12, 31)

    def test_metrics_preserved(self) -> None:
        metrics = _make_metrics(total_return=Decimal("0.25"))
        result = _make_result(prisma_metrics=metrics)
        assert result.prisma_metrics.total_return == Decimal("0.25")

    def test_series_preserved(self) -> None:
        series = _make_series(
            dates=[date(2024, 6, 30), date(2024, 7, 31)],
        )
        result = _make_result(series=series)
        assert result.series.dates == [date(2024, 6, 30), date(2024, 7, 31)]

    def test_immutability(self) -> None:
        result = _make_result()
        with pytest.raises(ValidationError):
            result.top_n = 5
