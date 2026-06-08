"""REST-Router für 3a-Eligibility unter /api/v1/stocks/{ticker}/3a-eligibility."""

from fastapi import APIRouter, Depends, HTTPException

from backend.application.services.swiss_market_service import SwissMarketService
from backend.interfaces.rest.dependencies import get_swiss_market_service
from backend.interfaces.rest.schemas.eligibility import EligibilityResponse

router = APIRouter(prefix="/api/v1", tags=["3a-eligibility"])


@router.get(
    "/stocks/{ticker}/3a-eligibility",
    response_model=EligibilityResponse,
    summary="3a-Eignung prüfen",
    description=(
        "Regelbasierter Filter (BVV2/FINMA): prüft ob ein Swiss Stock "
        "für die Schweizer Säule 3a (gebundene Vorsorge) geeignet ist. "
        "Keine Anlageberatung — rein regelbasiert."
    ),
)
async def get_3a_eligibility(
    ticker: str,
    service: SwissMarketService = Depends(get_swiss_market_service),
) -> EligibilityResponse:
    try:
        result = await service.check_3a_eligibility(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EligibilityResponse(
        ticker=result.ticker,
        eligible=result.eligible,
        reasons=list(result.reasons),
    )
