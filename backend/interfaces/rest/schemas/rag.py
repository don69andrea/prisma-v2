"""Pydantic-Schemas für RAG-Retrieval-Endpoint."""

import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrieveRequest(BaseModel):
    """Request für POST /api/v1/rag/retrieve."""

    query: str = Field(..., min_length=1, max_length=2000)
    k: int = Field(default=5, ge=1, le=20)
    ticker: str | None = Field(default=None)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        normalized = v.strip().upper()
        # Punkt-Ticker wie BRK.B oder BF.B erlaubt
        if not re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", normalized):
            raise ValueError("Ticker: 1–5 Grossbuchstaben, optional Punkt + Buchstabe (z.B. BRK.B)")
        return normalized


class ChunkResponse(BaseModel):
    """Ein einzelner Ähnlichkeits-Treffer."""

    chunk_id: UUID
    document_id: UUID
    chunk_idx: int
    content: str
    similarity: float = Field(..., ge=-1.0, le=1.0)
    ticker: str
    doc_type: str


class RetrieveResponse(BaseModel):
    """Response für POST /api/v1/rag/retrieve."""

    results: list[ChunkResponse]
    total: int
