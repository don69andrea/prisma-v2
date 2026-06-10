"""REST-Router für Fundamentaldaten unter /api/v1/stocks/{ticker}/fundamentals."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.errors import SwissDataUnavailableError
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.interfaces.rest.dependencies import get_yfinance_adapter
from backend.interfaces.rest.schemas.fundamentals import FundamentalsResponse

router = APIRouter(prefix="/api/v1", tags=["fundamentals"])


@router.get(
    "/stocks/{ticker}/fundamentals",
    response_model=FundamentalsResponse,
    summary="Fundamentaldaten abrufen",
    description=(
        "Liefert Bewertungskennzahlen (KGV, KBV, EPS, Dividendenrendite) "
        "für einen Swiss Stock via Yahoo Finance. "
        "Keine Anlageberatung — nur zu Informationszwecken."
    ),
)
async def get_fundamentals(
    ticker: str,
    adapter: YFinanceSwissAdapter = Depends(get_yfinance_adapter),
) -> FundamentalsResponse:
    try:
        data = await adapter.get_fundamentals(ticker)
    except SwissDataUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    raw_yield = data.dividend_yield
    yield_pct = round(float(raw_yield) * 100, 2) if raw_yield else None

    return FundamentalsResponse(
        ticker=ticker.upper(),
        pe_ratio=round(data.pe_ratio, 2) if data.pe_ratio is not None else None,
        pb_ratio=round(data.pb_ratio, 2) if data.pb_ratio is not None else None,
        eps_chf=round(data.eps_chf, 4) if data.eps_chf is not None else None,
        dividend_yield_pct=yield_pct,
        disclaimer=(
            "Bewertungskennzahlen via Yahoo Finance. Keine Anlageberatung. "
            "Daten können verzögert oder unvollständig sein."
        ),
    )
