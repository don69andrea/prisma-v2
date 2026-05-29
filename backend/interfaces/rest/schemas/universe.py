"""Pydantic-Schemas für Universe-Endpoints (Request/Response DTOs)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UniverseCreateRequest(BaseModel):
    name: str
    region: str
    tickers: list[str]

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name darf nicht leer sein")
        return v

    @field_validator("region")
    @classmethod
    def region_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("region darf nicht leer sein")
        return v.strip().upper()

    @field_validator("tickers")
    @classmethod
    def tickers_not_empty(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t.strip()]
        if not cleaned:
            raise ValueError("tickers darf nicht leer oder nur Whitespace sein")
        return cleaned


class UniverseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    region: str
    tickers: list[str]


class UniverseListResponse(BaseModel):
    items: list[UniverseRead]
    total: int


class UniverseSuggestionRequest(BaseModel):
    description: str = Field(..., min_length=3, max_length=500)


class UniverseSuggestionResponse(BaseModel):
    name: str
    region: str
    tickers: list[str]
    reasoning: str
    available_tickers: list[str]
