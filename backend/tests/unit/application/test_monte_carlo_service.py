"""Unit-Tests für MonteCarloService."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from backend.application.services.monte_carlo_service import (
    HoldingWeight,
    MonteCarloInput,
    MonteCarloResult,
    MonteCarloService,
    _run_gbm,
)

pytestmark = pytest.mark.unit


def _make_input(**kwargs: Any) -> MonteCarloInput:
    defaults: dict[str, Any] = dict(
        holdings=[HoldingWeight("NESN.SW", 0.6), HoldingWeight("NOVN.SW", 0.4)],
        monthly_contribution=588.0,
        years=30,
        initial_value=0.0,
        n_simulations=100,
    )
    defaults.update(kwargs)
    return MonteCarloInput(**defaults)


def _mock_params(n: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.array([0.0005] * n),
        np.array([0.012] * n),
        np.eye(n),
    )


@pytest.mark.asyncio
async def test_simulate_returns_correct_shape() -> None:
    svc = MonteCarloService()
    inp = _make_input(years=5, n_simulations=50)
    with patch.object(
        svc, "_fetch_return_params", new_callable=AsyncMock, return_value=_mock_params(2)
    ):
        result = await svc.simulate(inp)
    assert isinstance(result, MonteCarloResult)
    assert len(result.p5) == 60
    assert len(result.p50) == 60
    assert len(result.p95) == 60
    assert len(result.final_distribution) == 50
    assert result.months == 60
    assert result.contribution_total == pytest.approx(588.0 * 60)


@pytest.mark.asyncio
async def test_p5_le_p50_le_p95() -> None:
    svc = MonteCarloService()
    inp = _make_input(holdings=[HoldingWeight("NESN.SW", 1.0)], years=3, n_simulations=200)
    with patch.object(
        svc, "_fetch_return_params", new_callable=AsyncMock, return_value=_mock_params(1)
    ):
        result = await svc.simulate(inp)
    for p5, p50, p95 in zip(result.p5, result.p50, result.p95, strict=True):
        assert p5 <= p50 <= p95


@pytest.mark.asyncio
async def test_weights_not_summing_to_one_raises() -> None:
    svc = MonteCarloService()
    inp = MonteCarloInput(
        holdings=[HoldingWeight("NESN.SW", 0.6)],
        monthly_contribution=500.0,
        years=5,
        n_simulations=50,
    )
    with pytest.raises(ValueError, match="Gewichte"):
        await svc.simulate(inp)


@pytest.mark.asyncio
async def test_prob_bounds() -> None:
    svc = MonteCarloService()
    inp = _make_input(years=1, n_simulations=100)
    with patch.object(
        svc, "_fetch_return_params", new_callable=AsyncMock, return_value=_mock_params(2)
    ):
        result = await svc.simulate(inp)
    assert 0.0 <= result.prob_positive_return <= 1.0
    assert 0.0 <= result.prob_500k <= 1.0


def test_run_gbm_single_asset() -> None:
    inp = _make_input(holdings=[HoldingWeight("X", 1.0)], years=1, n_simulations=50)
    mu = np.array([0.0003])
    sigma = np.array([0.01])
    corr = np.array([[1.0]])
    result = _run_gbm(inp, mu, sigma, corr)
    assert len(result.p50) == 12
    assert all(v > 0 for v in result.p50)


from backend.application.services.monte_carlo_service import build_interpretation


def _make_result(
    p5_final: float = 95_000.0,
    p50_final: float = 285_000.0,
    p95_final: float = 420_000.0,
    initial_value: float = 100_000.0,
    contribution_total: float = 211_680.0,
    months: int = 240,
    prob_positive_return: float = 0.87,
) -> MonteCarloResult:
    return MonteCarloResult(
        p5=[p5_final] * months,
        p50=[p50_final] * months,
        p95=[p95_final] * months,
        final_distribution=[p50_final] * 100,
        prob_positive_return=prob_positive_return,
        prob_500k=0.12,
        contribution_total=contribution_total,
        months=months,
    )


def test_build_interpretation_contains_years() -> None:
    result = _make_result(months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "20 Jahren" in text or "20 Jahre" in text


def test_build_interpretation_contains_p5_and_p95() -> None:
    result = _make_result(p5_final=95_000.0, p95_final=420_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "95" in text or "95'000" in text
    assert "420" in text or "420'000" in text


def test_build_interpretation_contains_probability() -> None:
    result = _make_result(prob_positive_return=0.87, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "80" in text or "87" in text


def test_build_interpretation_contains_median() -> None:
    result = _make_result(p50_final=285_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "285" in text or "285'000" in text


def test_build_interpretation_gain_scenario() -> None:
    result = _make_result(p50_final=285_000.0, contribution_total=211_680.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "+" in text or "Gewinn" in text or "wächst" in text or "%" in text


def test_build_interpretation_worst_case_p5() -> None:
    result = _make_result(p5_final=95_000.0, initial_value=100_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "5" in text
    assert "95" in text or "95'000" in text


def test_build_interpretation_returns_str() -> None:
    result = _make_result(months=60)
    text = build_interpretation(result, initial_value=0.0, years=5)
    assert isinstance(text, str)
    assert len(text) > 50


def test_build_interpretation_zero_initial_value() -> None:
    result = _make_result(initial_value=0.0, p5_final=10_000.0, p50_final=80_000.0, p95_final=200_000.0, months=120)
    text = build_interpretation(result, initial_value=0.0, years=10)
    assert isinstance(text, str)
    assert len(text) > 20
