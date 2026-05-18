"""REST-Router für /api/v1/backtests."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.application.services.backtest_service import (
    BacktestService,
    NoResultsFound,
    RunNotFound,
)
from backend.interfaces.rest.dependencies import get_backtest_service
from backend.interfaces.rest.schemas.backtest import BacktestResultResponse, RunBacktestRequest

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


@router.post(
    "",
    response_model=BacktestResultResponse,
    summary="Backtest ausführen",
    description="Simuliert PRISMA Top-N, Universum und Benchmark über den angegebenen Zeitraum.",
)
async def run_backtest(
    body: RunBacktestRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> BacktestResultResponse:
    try:
        result = await service.run_backtest(
            model_run_id=body.model_run_id,
            start_date=body.start_date,
            end_date=body.end_date,
            top_n=body.top_n,
            benchmark_ticker=body.benchmark_ticker,
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoResultsFound as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BacktestResultResponse.from_entity(result)


@router.get(
    "/{result_id}",
    response_model=BacktestResultResponse,
    summary="Backtest-Ergebnis abrufen",
)
async def get_backtest_result(
    result_id: UUID,
    service: BacktestService = Depends(get_backtest_service),
) -> BacktestResultResponse:
    result = await service.get_backtest_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest-Ergebnis nicht gefunden") from None
    return BacktestResultResponse.from_entity(result)
