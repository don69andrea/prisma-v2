"""REST-Router für den Steuer-Implikations-Agenten unter /api/v1/steuer."""

from fastapi import APIRouter, Depends

from backend.application.agents.steuer_agent import SteuerAgent
from backend.interfaces.rest.dependencies import get_steuer_agent
from backend.interfaces.rest.schemas.steuer import (
    SteuerAnfrageRequest,
    SteuerEinschätzungResponse,
)

router = APIRouter(prefix="/api/v1/steuer", tags=["steuer-agent"])


@router.post(
    "/einschaetzung",
    response_model=SteuerEinschätzungResponse,
    summary="Steuer-Implikationen für eine CH-Aktienanlage",
    description=(
        "RAG-basierter Agent analysiert steuerliche Implikationen (Verrechnungssteuer, "
        "Einkommenssteuer, Vermögenssteuer) für eine Schweizer Aktienposition. "
        "⚠️ Keine Steuerberatung — immer einen Steuerberater konsultieren."
    ),
)
async def get_steuer_einschaetzung(
    request: SteuerAnfrageRequest,
    agent: SteuerAgent = Depends(get_steuer_agent),
) -> SteuerEinschätzungResponse:
    result = await agent.einschaetzen(
        ticker=request.ticker,
        anlegerprofil=request.anlegerprofil,
        halteperiode_jahre=request.halteperiode_jahre,
    )
    return SteuerEinschätzungResponse(
        ticker=result.ticker,
        anlegerprofil=result.anlegerprofil,
        halteperiode_jahre=result.halteperiode_jahre,
        steuerarten=result.steuerarten,
        pflichten=result.pflichten,
        hinweise=result.hinweise,
        quellen=result.quellen,
        disclaimer=result.disclaimer,
        generated_at=result.generated_at,
        model_version=result.model_version,
    )
