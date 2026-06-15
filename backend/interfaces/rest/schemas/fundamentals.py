"""Pydantic-Schema für Fundamentaldaten-Response."""

from __future__ import annotations

from pydantic import BaseModel


class FundamentalsResponse(BaseModel):
    """Response-Schema für GET /api/v1/stocks/{ticker}/fundamentals."""

    ticker: str
    pe_ratio: float | None
    pb_ratio: float | None
    eps_chf: float | None
    dividend_yield_pct: float | None
    fcf_yield: float | None = None
    operating_margin: float | None = None
    disclaimer: str
