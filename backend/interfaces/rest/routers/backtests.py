"""REST-Router für /api/v1/backtests."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.application.services.backtest_service import (
    BacktestService,
    NoResultsFound,
    RunNotFound,
)
from backend.application.services.signal_validation_service import SignalValidationService
from backend.interfaces.rest.dependencies import get_backtest_service, get_yfinance_adapter
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
            mode=body.mode,
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


signal_router = APIRouter(prefix="/api/v1/backtest", tags=["backtests"])


class SignalValidationResponse(BaseModel):
    return_pct: float
    buy_and_hold_pct: float
    win_rate_pct: float
    label: str


@signal_router.get(
    "/signal-validation/{ticker}",
    response_model=SignalValidationResponse,
    summary="Signal-Validierung",
    description=(
        "Mini-Backtest: Vergleicht PRISMA-Signal-Rendite mit Buy&Hold über 3 Jahre "
        "und gibt die Gewinn-Trade-Quote zurück."
    ),
)
async def get_signal_validation(
    ticker: str,
    adapter=Depends(get_yfinance_adapter),
) -> SignalValidationResponse:
    service = SignalValidationService(market_data_provider=adapter)
    result = await service.validate(ticker)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nicht genug historische Daten für {ticker}.",
        )
    return SignalValidationResponse(
        return_pct=result.return_pct,
        buy_and_hold_pct=result.buy_and_hold_pct,
        win_rate_pct=result.win_rate_pct,
        label=result.label,
    )
