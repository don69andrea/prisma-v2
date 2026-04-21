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
