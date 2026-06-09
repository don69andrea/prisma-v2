"""REST Router: Portfolio Intelligence API — POST /api/v1/portfolio/allocate."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.application.agents.portfolio_agent import PortfolioAgent
from backend.application.services.ranking_run_service import RankingRunNotFound, RankingRunService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.interfaces.rest.dependencies import (
    get_llm_client,
    get_ranking_run_service,
    get_swiss_stock_repository,
)
from backend.interfaces.rest.schemas.portfolio import (
    PortfolioAllocateRequest,
    PortfolioAllocationResponse,
    PortfolioPositionResponse,
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])
_logger = logging.getLogger(__name__)


def get_portfolio_agent(
    run_service: RankingRunService = Depends(get_ranking_run_service),
    swiss_repo: SwissStockRepository = Depends(get_swiss_stock_repository),
    llm_client: object = Depends(get_llm_client),
) -> PortfolioAgent:
    return PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=swiss_repo,
        yfinance_adapter=YFinanceSwissAdapter(),
        llm_client=llm_client,
    )


@router.post(
    "/allocate",
    response_model=PortfolioAllocationResponse,
    summary="Portfolio-Allokation aus Ranking-Run",
    description=(
        "Berechnet eine gewichtete Portfolio-Allokation aus den Top-N-Picks "
        "eines abgeschlossenen Ranking-Runs. Methoden: score_weighted (default) "
        "oder risk_parity (basierend auf 30d-Volatilität). "
        "LLM-Narrative Pydantic-validiert. Keine Anlageberatung."
    ),
)
async def allocate_portfolio(
    req: PortfolioAllocateRequest,
    agent: PortfolioAgent = Depends(get_portfolio_agent),
) -> PortfolioAllocationResponse:
    try:
        allocation = await agent.allocate(
            run_id=req.run_id,
            top_n=req.top_n,
            eligible_only=req.eligible_only,
            method=req.method,
        )
    except RankingRunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        _logger.exception("Portfolio-Allokation fehlgeschlagen für Run %s", req.run_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Portfolio-Berechnung fehlgeschlagen.",
        ) from exc

    return PortfolioAllocationResponse(
        run_id=allocation.run_id,
        method=allocation.method,
        positions=[
            PortfolioPositionResponse(
                ticker=p.ticker,
                weight=p.weight,
                quant_score=p.quant_score,
                is_3a_eligible=p.is_3a_eligible,
                rationale_de=p.rationale_de,
            )
            for p in allocation.positions
        ],
        overall_rationale_de=allocation.overall_rationale_de,
        computed_at=allocation.computed_at,
        eligible_only=allocation.eligible_only,
        total_positions=len(allocation.positions),
    )
