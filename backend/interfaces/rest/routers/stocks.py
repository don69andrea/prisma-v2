"""REST-Router für Stock-Endpunkte unter /api/v1/stocks."""

from fastapi import APIRouter, Depends, Query

from backend.application.services.stock_service import StockService
from backend.interfaces.rest.dependencies import get_stock_service
from backend.interfaces.rest.schemas.stock import StockListResponse, StockRead

router = APIRouter(prefix="/api/v1", tags=["stocks"])


@router.get(
    "/stocks",
    response_model=StockListResponse,
    summary="Alle Stocks auflisten",
    description="Gibt eine paginierte Liste aller im System bekannten Stocks zurück.",
)
async def list_stocks(
    limit: int = Query(
        default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse"
    ),
    offset: int = Query(
        default=0, ge=0, description="Anzahl zu überspringender Einträge"
    ),
    service: StockService = Depends(get_stock_service),
) -> StockListResponse:
    stocks = await service.list_stocks(limit=limit, offset=offset)
    items = [StockRead.model_validate(stock) for stock in stocks]
    return StockListResponse(items=items, total=len(items))
