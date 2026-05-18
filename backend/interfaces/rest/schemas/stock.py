"""Pydantic-Schemas für den REST-Layer (Request/Response DTOs)."""

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
