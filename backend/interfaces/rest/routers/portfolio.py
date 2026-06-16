"""REST Router: Portfolio Intelligence API — POST /api/v1/portfolio/allocate."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.application.agents.portfolio_agent import PortfolioAgent
from backend.application.services.monte_carlo_service import (
    HoldingWeight,
    MonteCarloInput,
    MonteCarloService,
    _run_gbm,
)
from backend.application.services.ranking_run_service import RankingRunNotFound, RankingRunService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.interfaces.rest.dependencies import (
    get_llm_client,
    get_ranking_run_service,
    get_swiss_stock_repository,
)
from backend.interfaces.rest.schemas.monte_carlo import MonteCarloRequest, MonteCarloResponse
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
    summary="KI-Portfolio-Allokation aus Ranking-Run (run_id-basiert)",
    description=(
        "Berechnet eine gewichtete Portfolio-Allokation als KI-Empfehlung aus den "
        "Top-N-Picks eines bereits abgeschlossenen Ranking-Runs (`run_id`). "
        "Methoden: score_weighted (default), risk_parity (basierend auf "
        "30d-Volatilität) oder mean_variance (Markowitz Mean-Variance mit "
        "Ledoit-Wolf Shrinkage, maximiert Sharpe Ratio). "
        "LLM-Narrative Pydantic-validiert. Keine Anlageberatung.\n\n"
        "Hinweis: Dieser Endpoint erwartet ausschliesslich einen `run_id`-Verweis "
        "auf einen bestehenden Ranking-Run — keine direkte Eingabe eigener Ticker "
        "oder Stückzahlen. Für die Verwaltung eines eigenen, bereits bestehenden "
        "Portfolios (Ist-/Soll-Gewichte je Ticker) siehe stattdessen "
        "`POST /api/v1/portfolio/rebalance`."
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


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResponse,
    summary="Monte Carlo 3a Retirement Simulator",
    description="Simuliert N Wealth-Paths (GBM) für ein Portfolio über 1–40 Jahre. Keine Anlageberatung.",
)
async def monte_carlo(req: MonteCarloRequest) -> MonteCarloResponse:
    svc = MonteCarloService()
    inp = MonteCarloInput(
        holdings=[HoldingWeight(ticker=h.ticker, weight=h.weight) for h in req.holdings],
        monthly_contribution=req.monthly_contribution,
        years=req.years,
        initial_value=req.initial_value,
        n_simulations=req.n_simulations,
    )
    try:
        # W-2: Fetch stochastic parameters async, then offload CPU-intensive GBM
        # simulation (up to 50k paths × N months) to a thread to avoid blocking
        # the event loop.
        total_weight = sum(h.weight for h in inp.holdings)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Gewichte müssen 1.0 ergeben, ist: {total_weight:.3f}")
        mu_arr, sigma_arr, corr_matrix = await svc._fetch_return_params(inp.holdings)
        result = await asyncio.to_thread(_run_gbm, inp, mu_arr, sigma_arr, corr_matrix)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return MonteCarloResponse(
        p5=result.p5,
        p50=result.p50,
        p95=result.p95,
        final_distribution=result.final_distribution,
        prob_positive_return=result.prob_positive_return,
        prob_500k=result.prob_500k,
        contribution_total=result.contribution_total,
        months=result.months,
        correlation_degraded=result.correlation_degraded,
        interpretation=result.interpretation,
    )
