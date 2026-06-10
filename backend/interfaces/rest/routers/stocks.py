"""REST-Router für Stock-Endpunkte unter /api/v1/stocks."""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.factsheet_service import FactsheetService
from backend.application.services.stock_service import StockNotFound, StockService
from backend.application.services.swiss_market_service import SwissMarketService
from backend.interfaces.rest.dependencies import (
    get_factsheet_service,
    get_stock_service,
    get_swiss_market_service,
)
from backend.interfaces.rest.schemas.langfrist import LangfristScoreResponse
from backend.interfaces.rest.schemas.stock import (
    LatestRankingSnapshot,
    PricePoint,
    PriceSeriesResponse,
    StockFactsheet,
    StockListResponse,
    StockRead,
)

router = APIRouter(prefix="/api/v1", tags=["stocks"])


@router.get(
    "/stocks/{ticker}",
    response_model=StockRead,
    summary="Stock per Ticker abrufen",
    description="Gibt einen einzelnen Stock anhand des Ticker-Symbols zurück (case-insensitive).",
)
async def get_stock_by_ticker(
    ticker: str,
    service: StockService = Depends(get_stock_service),
) -> StockRead:
    stock = await service.get_by_ticker(ticker)
    if stock is None:
        raise HTTPException(
            status_code=404, detail=f"Stock '{ticker.upper()}' nicht gefunden"
        ) from None
    return StockRead.model_validate(stock)


@router.get(
    "/stocks",
    response_model=StockListResponse,
    summary="Alle Stocks auflisten",
    description="Gibt eine paginierte Liste aller im System bekannten Stocks zurück.",
)
async def list_stocks(
    limit: int = Query(default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse"),
    offset: int = Query(default=0, ge=0, description="Anzahl zu überspringender Einträge"),
    exchange: str | None = Query(default=None, description="Filter: 'XSWX' für Swiss Stocks"),
    service: StockService = Depends(get_stock_service),
    swiss_service: SwissMarketService = Depends(get_swiss_market_service),
) -> StockListResponse:
    if exchange == "XSWX":
        all_swiss = await swiss_service.list_smi_stocks()
        paginated = all_swiss[offset : offset + limit]
        items = [
            StockRead(
                id=s.id,
                ticker=s.ticker,
                name=s.name,
                isin=s.isin,
                sector=s.sector,
                country="CH",
                currency=s.currency,
                exchange=s.exchange,
                market_cap_chf=s.market_cap_chf,
            )
            for s in paginated
        ]
        return StockListResponse(items=items, total=len(all_swiss))
    stocks = await service.list_stocks(limit=limit, offset=offset, exchange=exchange)
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


@router.get(
    "/stocks/{ticker}/prices",
    response_model=PriceSeriesResponse,
    summary="Preiszeitreihe abrufen",
    description="Gibt die letzten `days` Handelstage als Preiszeitreihe zurück (Stub-Daten).",
)
async def get_prices(
    ticker: str,
    days: int = Query(default=252, ge=1, le=504, description="Anzahl Handelstage, 1–504"),
    service: StockService = Depends(get_stock_service),
) -> PriceSeriesResponse:
    try:
        ticker_upper, prices = await service.get_price_series(ticker, days)
    except StockNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PriceSeriesResponse(
        ticker=ticker_upper,
        prices=[PricePoint(date=str(p["date"]), close=float(p["close"])) for p in prices],
    )


@router.get(
    "/stocks/{ticker}/langfrist-score",
    response_model=LangfristScoreResponse,
    summary="VIAC Langfrist-Score (0–10)",
    description=(
        "Berechnet den 30-Jahres-Vorsorge-Score aus Dividendenstabilität, "
        "Bilanzqualität, Kursvolatilität und Marktkapitalisierung. "
        "Keine Anlageberatung — rein modellbasiert."
    ),
)
async def get_langfrist_score(
    ticker: str,
    service: SwissMarketService = Depends(get_swiss_market_service),
) -> LangfristScoreResponse:
    try:
        score = await service.score_langfrist(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LangfristScoreResponse(
        ticker=score.ticker,
        value=score.value,
        components=score.components,
        explanation=score.explanation,
    )
