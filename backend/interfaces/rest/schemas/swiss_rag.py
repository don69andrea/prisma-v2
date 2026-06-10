"""Pydantic-Schemas für POST /api/v1/rag/swiss/retrieve."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class SwissRagRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    ticker: str | None = Field(default=None, max_length=10)
    language: str | None = Field(default=None, pattern=r"^(de|en|fr)$")


class SwissRagChunkResult(BaseModel):
    chunk_id: UUID
    chunk_idx: int
    url: str
    ticker: str
    source: str
    language: str
    filing_date: date
    doc_type: str
    content: str
    similarity: float


class SwissRagRetrieveResponse(BaseModel):
    results: list[SwissRagChunkResult]
    total: int
