"""Unit-Tests für RebalancingService."""

from __future__ import annotations

import pytest

from backend.application.services.rebalancing_service import RebalancingService


@pytest.mark.asyncio
async def test_buy_step_when_underweight() -> None:
    svc = RebalancingService()
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={"NESN": 0.20},
        target_weights={"NESN": 0.40},
    )
    step = next(s for s in plan.steps if s.ticker == "NESN")
    assert step.action == "BUY"
    assert abs(step.delta_weight - 0.20) < 1e-9


@pytest.mark.asyncio
async def test_sell_step_when_overweight() -> None:
    svc = RebalancingService()
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={"NOVN": 0.50},
        target_weights={"NOVN": 0.20},
    )
    step = next(s for s in plan.steps if s.ticker == "NOVN")
    assert step.action == "SELL"
    assert abs(step.delta_weight - (-0.30)) < 1e-9


@pytest.mark.asyncio
async def test_hold_step_within_threshold() -> None:
    svc = RebalancingService()
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={"ABBN": 0.25},
        target_weights={"ABBN": 0.252},  # delta = 0.002 < 0.005
    )
    step = next(s for s in plan.steps if s.ticker == "ABBN")
    assert step.action == "HOLD"
    assert step.transaction_cost_chf == 0.0


@pytest.mark.asyncio
async def test_transaction_cost_calculation() -> None:
    svc = RebalancingService(transaction_cost_rate=0.001)
    plan = await svc.compute_plan(
        total_portfolio_value_chf=100_000.0,
        current_weights={"NESN": 0.10},
        target_weights={"NESN": 0.20},
    )
    step = next(s for s in plan.steps if s.ticker == "NESN")
    # delta=0.10, value=10_000 CHF, cost=10_000 * 0.001 = 10.0
    assert abs(step.estimated_value_chf - 10_000.0) < 0.01
    assert abs(step.transaction_cost_chf - 10.0) < 0.01


@pytest.mark.asyncio
async def test_total_cost_is_sum_of_steps() -> None:
    svc = RebalancingService(transaction_cost_rate=0.001)
    plan = await svc.compute_plan(
        total_portfolio_value_chf=50_000.0,
        current_weights={"NESN": 0.30, "NOVN": 0.30},
        target_weights={"NESN": 0.40, "NOVN": 0.20},
    )
    expected_total = sum(s.transaction_cost_chf for s in plan.steps)
    assert abs(plan.total_transaction_cost_chf - expected_total) < 1e-9


@pytest.mark.asyncio
async def test_ticker_only_in_target_gets_buy() -> None:
    svc = RebalancingService()
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={},
        target_weights={"ZURN": 0.15},
    )
    step = next(s for s in plan.steps if s.ticker == "ZURN")
    assert step.action == "BUY"
    assert step.current_weight == 0.0


@pytest.mark.asyncio
async def test_ticker_only_in_current_gets_sell() -> None:
    svc = RebalancingService()
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={"LONN": 0.10},
        target_weights={},
    )
    step = next(s for s in plan.steps if s.ticker == "LONN")
    assert step.action == "SELL"
    assert step.target_weight == 0.0


@pytest.mark.asyncio
async def test_no_stock_repo_means_not_3a_eligible_in_3a_mode() -> None:
    svc = RebalancingService(stock_repo=None)
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={"NESN": 0.20},
        target_weights={"NESN": 0.30},
        is_3a_account=True,
    )
    step = next(s for s in plan.steps if s.ticker == "NESN")
    assert step.is_3a_eligible is False


@pytest.mark.asyncio
async def test_non_3a_account_marks_all_as_eligible() -> None:
    svc = RebalancingService(stock_repo=None)
    plan = await svc.compute_plan(
        total_portfolio_value_chf=10_000.0,
        current_weights={"NESN": 0.20},
        target_weights={"NESN": 0.30},
        is_3a_account=False,
    )
    step = next(s for s in plan.steps if s.ticker == "NESN")
    assert step.is_3a_eligible is True


@pytest.mark.asyncio
async def test_plan_metadata() -> None:
    svc = RebalancingService()
    plan = await svc.compute_plan(
        total_portfolio_value_chf=20_000.0,
        current_weights={"NESN": 0.50},
        target_weights={"NESN": 0.50},
        is_3a_account=True,
    )
    assert plan.total_portfolio_value_chf == 20_000.0
    assert plan.is_3a_account is True
    assert plan.plan_id is not None
    assert plan.computed_at is not None
