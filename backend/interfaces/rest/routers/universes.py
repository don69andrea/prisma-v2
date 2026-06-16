"""REST-Router für Universe-Endpunkte unter /api/v1/universes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.application.services.universe_service import UniverseNotFound, UniverseService
from backend.application.services.universe_suggestion_service import (
    EmptySuggestion,
    InvalidLLMOutput,
    UniverseSuggestionService,
)
from backend.domain.repositories.universe_repository import DuplicateUniverseNameError
from backend.interfaces.rest.dependencies import (
    get_universe_service,
    get_universe_suggestion_service,
)
from backend.interfaces.rest.schemas.universe import (
    UniverseCreateRequest,
    UniverseListResponse,
    UniverseRead,
    UniverseSuggestionRequest,
    UniverseSuggestionResponse,
    UniverseSyncResponse,
)

router = APIRouter(prefix="/api/v1/universes", tags=["universes"])


@router.get(
    "",
    response_model=UniverseListResponse,
    summary="Alle Universen auflisten",
)
async def list_universes(
    service: UniverseService = Depends(get_universe_service),
) -> UniverseListResponse:
    universes = await service.list_universes()
    items = [
        UniverseRead(id=u.id, name=u.name, region=u.region, tickers=list(u.tickers))
        for u in universes
    ]
    return UniverseListResponse(items=items, total=len(items))


@router.get(
    "/{universe_id}",
    response_model=UniverseRead,
    summary="Einzelnes Universum abrufen",
)
async def get_universe(
    universe_id: UUID,
    service: UniverseService = Depends(get_universe_service),
) -> UniverseRead:
    try:
        universe = await service.get_universe(universe_id)
    except UniverseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return UniverseRead(
        id=universe.id, name=universe.name, region=universe.region, tickers=list(universe.tickers)
    )


@router.post(
    "",
    status_code=201,
    response_model=UniverseRead,
    summary="Neues Universum anlegen",
)
async def create_universe(
    request: UniverseCreateRequest,
    service: UniverseService = Depends(get_universe_service),
) -> UniverseRead:
    try:
        universe = await service.create_universe(
            name=request.name,
            region=request.region,
            tickers=request.tickers,
        )
    except DuplicateUniverseNameError as exc:
        raise HTTPException(
            status_code=409,
            detail="Ein Universe mit diesem Namen existiert bereits.",
        ) from exc
    return UniverseRead(
        id=universe.id, name=universe.name, region=universe.region, tickers=list(universe.tickers)
    )


@router.post(
    "/{universe_id}/sync",
    response_model=UniverseSyncResponse,
    summary="Ticker-Daten für ein Universum synchronisieren",
)
async def sync_universe(
    universe_id: UUID,
    service: UniverseService = Depends(get_universe_service),
) -> UniverseSyncResponse:
    try:
        result = await service.sync_universe(universe_id=universe_id)
    except UniverseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return UniverseSyncResponse(
        universe_id=result.universe_id,
        synced_count=result.synced_count,
        failed_tickers=result.failed_tickers,
    )


@router.post(
    "/suggest",
    response_model=UniverseSuggestionResponse,
    summary="Universe-Vorschlag via Claude generieren",
)
async def suggest_universe(
    request: UniverseSuggestionRequest,
    service: UniverseSuggestionService = Depends(get_universe_suggestion_service),
) -> UniverseSuggestionResponse:
    try:
        suggestion = await service.suggest(description=request.description)
    except EmptySuggestion as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidLLMOutput as exc:
        raise HTTPException(status_code=502, detail=f"LLM-Output ungültig: {exc}") from exc
    return UniverseSuggestionResponse(
        name=suggestion.name,
        region=suggestion.region,
        tickers=suggestion.tickers,
        reasoning=suggestion.reasoning,
        available_tickers=suggestion.available_tickers,
    )
