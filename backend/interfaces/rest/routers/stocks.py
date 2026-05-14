"""REST-Router für Stock-Endpunkte unter /api/v1/stocks."""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.factsheet_service import FactsheetService, StockNotFound
from backend.application.services.stock_service import StockService
from backend.interfaces.rest.dependencies import get_factsheet_service, get_stock_service
from backend.interfaces.rest.schemas.stock import (
    LatestRankingSnapshot,
    StockFactsheet,
    StockListResponse,
    StockRead,
)

router = APIRouter(prefix="/api/v1", tags=["stocks"])


@router.get(
    "/stocks",
    response_model=StockListResponse,
    summary="Alle Stocks auflisten",
    description="Gibt eine paginierte Liste aller im System bekannten Stocks zurück.",
)
async def list_stocks(
    limit: int = Query(default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse"),
    offset: int = Query(default=0, ge=0, description="Anzahl zu überspringender Einträge"),
    service: StockService = Depends(get_stock_service),
) -> StockListResponse:
    stocks = await service.list_stocks(limit=limit, offset=offset)
    items = [StockRead.model_validate(stock) for stock in stocks]
    return StockListResponse(items=items, total=len(items))


@router.get(
    "/stocks/{ticker}/factsheet",
    response_model=StockFactsheet,
    summary="Stock-Factsheet abrufen",
    description="Gibt Stammdaten und neueste Ranking-Momentaufnahme für einen Ticker zurück.",
)
async def get_factsheet(
    ticker: str,
    service: FactsheetService = Depends(get_factsheet_service),
) -> StockFactsheet:
    try:
        stock, raw = await service.get_factsheet(ticker)
    except StockNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = LatestRankingSnapshot.model_validate(raw) if raw is not None else None
    return StockFactsheet(stock=StockRead.model_validate(stock), latest_ranking=snapshot)
