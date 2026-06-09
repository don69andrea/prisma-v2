"""Rebalancing-Plan Value Objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class RebalancingStep:
    """Eine einzelne Transaktion im Rebalancing-Plan."""

    ticker: str
    action: Literal["BUY", "SELL", "HOLD"]
    current_weight: float
    target_weight: float
    delta_weight: float
    estimated_value_chf: float
    transaction_cost_chf: float
    is_3a_eligible: bool


@dataclass(frozen=True)
class RebalancingPlan:
    """Vollständiger Rebalancing-Plan für ein Portfolio."""

    plan_id: UUID
    steps: tuple[RebalancingStep, ...]
    total_portfolio_value_chf: float
    total_transaction_cost_chf: float
    is_3a_account: bool
    computed_at: datetime
