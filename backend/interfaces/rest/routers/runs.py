"""FastAPI-Router für /api/v1/runs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.ranking_run_service import (
    RankingRunNotFound,
    RankingRunService,
    UniverseNotFound,
)
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.interfaces.rest.dependencies import (
    get_ranking_run_service,
    get_universe_repository,
    require_api_key,
)
from backend.interfaces.rest.schemas.runs import PostRunRequest, RankingItem, RunResponse

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


async def _universe_name(
    universe_repo: UniverseRepository,
    universe_id: UUID,
) -> str:
    universe = await universe_repo.get(universe_id)
    return universe.name if universe is not None else "(deleted)"


@router.get("", response_model=list[RunResponse])
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: RankingRunService = Depends(get_ranking_run_service),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
) -> list[RunResponse]:
    runs = await service.list_runs(limit=limit, offset=offset)
    return [
        RunResponse.from_domain(r, await _universe_name(universe_repo, r.universe_id)) for r in runs
    ]


@router.post("", status_code=201, response_model=RunResponse)
async def post_run(
    request: PostRunRequest,
    service: RankingRunService = Depends(get_ranking_run_service),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    _auth: None = Depends(require_api_key),
) -> RunResponse:
    try:
        run = await service.create_and_execute_run(
            universe_id=request.universe_id,
            weight_config=request.to_weight_config(),
        )
    except UniverseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunResponse.from_domain(run, await _universe_name(universe_repo, run.universe_id))


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    service: RankingRunService = Depends(get_ranking_run_service),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
) -> RunResponse:
    try:
        run = await service.get_run(run_id)
    except RankingRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunResponse.from_domain(run, await _universe_name(universe_repo, run.universe_id))


@router.get("/{run_id}/rankings", response_model=list[RankingItem])
async def get_rankings(
    run_id: UUID,
    service: RankingRunService = Depends(get_ranking_run_service),
) -> list[RankingItem]:
    try:
        results = await service.get_rankings(run_id)
    except RankingRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [RankingItem.model_validate(r) for r in results]
