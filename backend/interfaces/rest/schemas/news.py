"""Pydantic-Schemas für News-RAG-Endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class NewsIngestResponse(BaseModel):
    ingested: int
    skipped_duplicate: int
    errors: int


class NewsRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=20)
    ticker: str | None = Field(default=None, description="Optionaler Ticker-Filter")


class NewsChunkResult(BaseModel):
    chunk_id: str
    news_document_id: str
    chunk_idx: int
    content: str
    similarity: float
    title: str
    source: str
    tickers: list[str]
    published_at: datetime | None


class NewsRetrieveResponse(BaseModel):
    results: list[NewsChunkResult]
    total: int
