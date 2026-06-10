"""REST-Router für Dividendendaten unter /api/v1/stocks/{ticker}/dividends."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.errors import SwissDataUnavailableError
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.interfaces.rest.dependencies import get_yfinance_adapter
from backend.interfaces.rest.schemas.dividends import DividendEntry, DividendResponse

router = APIRouter(prefix="/api/v1", tags=["dividends"])


@router.get(
    "/stocks/{ticker}/dividends",
    response_model=DividendResponse,
    summary="Dividendendaten abrufen",
    description=(
        "Liefert aktuelle Dividendendaten (Rendite, letzte Ausschüttung, Ex-Datum) "
        "sowie historische Ausschüttungen der letzten Jahre via Yahoo Finance. "
        "Keine Anlageberatung — nur zu Informationszwecken."
    ),
)
async def get_dividends(
    ticker: str,
    adapter: YFinanceSwissAdapter = Depends(get_yfinance_adapter),
) -> DividendResponse:
    try:
        data = await adapter.get_dividends(ticker)
    except SwissDataUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DividendResponse(
        ticker=data.ticker,
        last_dividend_chf=data.last_dividend_chf,
        ex_date=data.ex_date,
        dividend_yield_pct=data.dividend_yield_pct,
        history=[DividendEntry(date=e.date, amount_chf=e.amount_chf) for e in data.history],
        disclaimer=data.disclaimer,
    )
