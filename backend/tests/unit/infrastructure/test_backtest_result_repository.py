"""Unit-Tests für die Serialisierungs-Helpers des BacktestResultRepository."""

from datetime import date
from decimal import Decimal

import pytest

from backend.domain.entities.backtest_result import BacktestSeries, PortfolioMetrics
from backend.infrastructure.persistence.repositories.backtest_result_repository import (
    _metrics_from_dict,
    _metrics_to_dict,
    _series_from_dict,
    _series_to_dict,
)

pytestmark = pytest.mark.unit


def test_metrics_roundtrip() -> None:
    m = PortfolioMetrics(
        total_return=Decimal("0.123456789"),
        cagr=Decimal("0.075"),
        annual_vol=Decimal("0.12"),
        sharpe=Decimal("0.625"),
        max_drawdown=Decimal("0.08"),
    )
    assert _metrics_from_dict(_metrics_to_dict(m)) == m


def test_series_roundtrip() -> None:
    s = BacktestSeries(
        dates=[date(2024, 1, 31), date(2024, 2, 29)],
        prisma=[Decimal("1.0"), Decimal("1.05")],
        universe=[Decimal("1.0"), Decimal("1.03")],
        benchmark=[Decimal("1.0"), Decimal("1.02")],
    )
    assert _series_from_dict(_series_to_dict(s)) == s
