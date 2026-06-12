"""REST Router: Decision Intelligence API — GET /api/v1/decisions."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.application.agents.macro_agent import MacroIntelligenceAgent
from backend.application.services.macro_service import MacroService
from backend.application.services.signal_aggregation_service import SignalAggregationService
from backend.application.services.universe_service import UniverseNotFound, UniverseService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.interfaces.rest.dependencies import (
    get_llm_client,
    get_swiss_stock_repository,
    get_universe_service,
)
from backend.interfaces.rest.schemas.decision import DecisionListResponse, DecisionSignalResponse

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])
_logger = logging.getLogger(__name__)


def get_signal_aggregation_service(
    swiss_stock_repo: SwissStockRepository = Depends(get_swiss_stock_repository),
    llm_client: object = Depends(get_llm_client),
) -> SignalAggregationService:
    macro_agent = MacroIntelligenceAgent(macro_service=MacroService(llm_client=llm_client))
    return SignalAggregationService(swiss_stock_repo=swiss_stock_repo, macro_agent=macro_agent)


@router.get(
    "",
    response_model=DecisionListResponse,
    summary="BUY/HOLD/WATCH Signale für ein Universum",
    description=(
        "Berechnet aggregierte Handelssignale (Quant 45% + ML 35% + Macro 20%) "
        "für alle Ticker eines Universums. Optionale Filter: signal-Typ, 3a-Eligible. "
        "Signale ohne Marktdaten werden übersprungen."
    ),
)
async def list_decisions(
    universe_id: UUID = Query(..., description="Universum-ID"),
    signal: str | None = Query(default=None, description="Filter: BUY | HOLD | WATCH"),
    eligible_only: bool = Query(default=False, description="Nur 3a-eligible Titel zurückgeben"),
    universe_service: UniverseService = Depends(get_universe_service),
    aggregation_service: SignalAggregationService = Depends(get_signal_aggregation_service),
) -> DecisionListResponse:
    try:
        universe = await universe_service.get_universe(universe_id)
    except UniverseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    tickers = list(universe.tickers)
    signals = await aggregation_service.get_signals(tickers)

    if signal is not None:
        signal_upper = signal.upper()
        if signal_upper not in {"BUY", "HOLD", "WATCH"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="signal muss BUY, HOLD oder WATCH sein.",
            )
        signals = [s for s in signals if s.signal == signal_upper]

    if eligible_only:
        signals = [s for s in signals if s.is_3a_eligible]

    items = [
        DecisionSignalResponse(
            ticker=s.ticker,
            snapshot_date=s.snapshot_date,
            signal=s.signal,
            confidence=s.confidence,
            weighted_score=s.weighted_score,
            quant_score=s.quant_score,
            ml_score=s.ml_score,
            macro_score=s.macro_score,
            is_3a_eligible=s.is_3a_eligible,
        )
        for s in signals
    ]

    return DecisionListResponse(items=items, total=len(items))
