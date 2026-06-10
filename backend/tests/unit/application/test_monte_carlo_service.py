"""Unit-Tests für MonteCarloService."""

from __future__ import annotations

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


def _make_input(**kwargs) -> MonteCarloInput:
    defaults = dict(
        holdings=[HoldingWeight("NESN.SW", 0.6), HoldingWeight("NOVN.SW", 0.4)],
        monthly_contribution=588.0,
        years=30,
        initial_value=0.0,
        n_simulations=100,
    )
    defaults.update(kwargs)
    return MonteCarloInput(**defaults)


def _mock_params(n: int = 2):
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
