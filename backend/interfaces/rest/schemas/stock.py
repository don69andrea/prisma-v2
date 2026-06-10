"""Pydantic-Schemas für den REST-Layer (Request/Response DTOs)."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StockRead(BaseModel):
    """Serialisierungsschema für eine einzelne Stock-Entität in API-Responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    name: str
    isin: str | None
    sector: str | None
    country: str | None
    currency: str
    exchange: str | None = None
    market_cap_chf: Decimal | None = None


class StockListResponse(BaseModel):
    """Wrapper für paginierte Stock-Listen mit Gesamtanzahl."""

    items: list[StockRead]
    total: int


class LatestRankingSnapshot(BaseModel):
    """Ranking-Ergebnis eines Tickers aus dem neuesten abgeschlossenen Run."""

    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool
    per_model_ranks: dict[str, int | None]


class StockFactsheet(BaseModel):
    """Kombiniertes Factsheet: Stock-Stammdaten + neueste Ranking-Momentaufnahme."""

    stock: StockRead
    latest_ranking: LatestRankingSnapshot | None


class PricePoint(BaseModel):
    """Ein Datenpunkt in einer Preiszeitreihe."""

    date: str  # ISO-8601, z.B. "2025-05-18"
    close: float


class PriceSeriesResponse(BaseModel):
    """Preiszeitreihe für einen einzelnen Ticker."""

    ticker: str
    prices: list[PricePoint]


class FundamentalsRead(BaseModel):
    """Fundamentaldaten-Snapshot für einen Ticker (Swiss-Daten via yfinance)."""

    ticker: str
    pe_ratio: float | None
    pb_ratio: float | None
    eps_chf: float | None
    dividend_yield_pct: float | None
    disclaimer: str


class EligibilityRead(BaseModel):
    ticker: str
    eligible: bool
    reasons: list[str]
    disclaimer: str
