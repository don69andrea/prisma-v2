"""REST-Router für Portfolio-Rebalancing unter /api/v1/portfolio/rebalance."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.application.services.rebalancing_service import RebalancingService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.interfaces.rest.dependencies import get_swiss_stock_repository
from backend.interfaces.rest.schemas.rebalancing import (
    RebalancingPlanResponse,
    RebalancingRequest,
    RebalancingStepResponse,
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["rebalancing"])


@router.post(
    "/rebalance",
    response_model=RebalancingPlanResponse,
    summary="Rebalancing-Plan berechnen",
    description=(
        "Berechnet Kauf-/Verkauf-Schritte um ein Portfolio von der Ist- zur Soll-Allokation "
        "zu bringen. Inklusive Transaktionskostenschätzung. "
        "Mit is_3a_account=true werden nur BVV2/FINMA-geeignete Titel empfohlen. "
        "Keine Anlageberatung."
    ),
)
async def compute_rebalancing_plan(
    body: RebalancingRequest,
    swiss_repo: SwissStockRepository = Depends(get_swiss_stock_repository),
) -> RebalancingPlanResponse:
    service = RebalancingService(
        transaction_cost_rate=body.transaction_cost_rate,
        stock_repo=swiss_repo,
    )
    plan = await service.compute_plan(
        total_portfolio_value_chf=body.total_portfolio_value_chf,
        current_weights=body.current_weights,
        target_weights=body.target_weights,
        is_3a_account=body.is_3a_account,
    )
    return RebalancingPlanResponse(
        plan_id=plan.plan_id,
        steps=[
            RebalancingStepResponse(
                ticker=s.ticker,
                action=s.action,
                current_weight=s.current_weight,
                target_weight=s.target_weight,
                delta_weight=s.delta_weight,
                estimated_value_chf=s.estimated_value_chf,
                transaction_cost_chf=s.transaction_cost_chf,
                is_3a_eligible=s.is_3a_eligible,
            )
            for s in plan.steps
        ],
        total_portfolio_value_chf=plan.total_portfolio_value_chf,
        total_transaction_cost_chf=plan.total_transaction_cost_chf,
        is_3a_account=plan.is_3a_account,
        computed_at=plan.computed_at,
    )
