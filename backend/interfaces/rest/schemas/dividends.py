"""Pydantic-Schema für Dividenden-Response."""

from __future__ import annotations

from pydantic import BaseModel


class DividendEntry(BaseModel):
    """Einzelne Dividendenausschüttung."""

    date: str
    amount_chf: float


class DividendResponse(BaseModel):
    """Response-Schema für GET /api/v1/stocks/{ticker}/dividends."""

    ticker: str
    last_dividend_chf: float | None
    ex_date: str | None
    dividend_yield_pct: float | None
    history: list[DividendEntry]
    disclaimer: str
