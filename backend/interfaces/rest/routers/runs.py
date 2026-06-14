"""FastAPI-Router für /api/v1/runs."""

import asyncio
import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.application.services.ranking_run_service import (
    RankingRunNotFound,
    RankingRunService,
    UniverseNotFound,
)
from backend.application.services.stock_service import StockService
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.interfaces.rest.dependencies import (
    get_ranking_run_service,
    get_stock_service,
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
    names = await asyncio.gather(*[_universe_name(universe_repo, r.universe_id) for r in runs])
    return [RunResponse.from_domain(r, name) for r, name in zip(runs, names, strict=True)]


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


@router.get(
    "/{run_id}/export",
    summary="Rankings als CSV exportieren",
    description=(
        "Gibt alle Rankings eines abgeschlossenen Runs als CSV-Datei zurueck. "
        "Spalten: rank, ticker, name, sector, weighted_avg, is_sweet_spot sowie eine Spalte "
        "pro Modell aus per_model_ranks."
    ),
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_rankings_csv(
    run_id: UUID,
    export_format: str = Query("csv", alias="format", pattern="^csv$"),
    service: RankingRunService = Depends(get_ranking_run_service),
    stock_service: StockService = Depends(get_stock_service),
) -> Response:
    try:
        results = await service.get_rankings(run_id)
    except RankingRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    items = [RankingItem.model_validate(r) for r in results]
    all_models = sorted({m for item in items for m in item.per_model_ranks})

    stocks = await asyncio.gather(
        *[stock_service.get_by_ticker(item.ticker) for item in items],
        return_exceptions=True,
    )
    stock_map = {
        item.ticker: s
        for item, s in zip(items, stocks, strict=True)
        if not isinstance(s, Exception) and s is not None
    }

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["rank", "ticker", "name", "sector", "weighted_avg", "is_sweet_spot", *all_models]
    )
    for item in items:
        stock = stock_map.get(item.ticker)
        writer.writerow(
            [
                item.total_rank if item.total_rank is not None else "",
                item.ticker,
                stock.name if stock else "",
                (stock.sector or "") if stock else "",
                f"{item.weighted_avg:.4f}" if item.weighted_avg is not None else "",
                "true" if item.is_sweet_spot else "false",
                *[item.per_model_ranks.get(m) or "" for m in all_models],
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="rankings_{run_id}.csv"'},
    )
