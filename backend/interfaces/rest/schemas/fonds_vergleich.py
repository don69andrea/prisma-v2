"""Pydantic-Schemas für Fonds-Vergleich API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class FondsPosition(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    weight: float = Field(default=1.0, gt=0.0)


class FondsVergleichRequest(BaseModel):
    fonds_name: str = Field(..., min_length=1)
    positions: list[FondsPosition] = Field(..., min_length=1, max_length=20)
    lookback_years: int = Field(default=3, ge=1, le=10)


class PortfolioMetricsResponse(BaseModel):
    expected_return_pa: Decimal
    volatility_pa: Decimal
    sharpe_ratio: Decimal | None
    max_drawdown: Decimal


class FondsVergleichResponse(BaseModel):
    fonds_name: str
    fonds_metrics: PortfolioMetricsResponse
    custom_metrics: PortfolioMetricsResponse
    snapshot_date: date
    disclaimer: str


class ViacFondsItem(BaseModel):
    name: str
    description: str
    equity_ratio: float
