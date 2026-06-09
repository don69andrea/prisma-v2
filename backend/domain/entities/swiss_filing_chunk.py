"""Domain-Entity: Swiss Filing Chunk (swiss_rag_chunks)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

EMBEDDING_DIM = 2048


@dataclass(frozen=True)
class SwissFilingChunk:
    id: UUID
    url_hash: str  # SHA-256 of source PDF URL — deduplication key per chunk
    url: str  # source PDF URL
    ticker: str
    source: str  # "SIX" | "IR"
    language: str  # "de" | "en" | "fr"
    filing_date: date
    doc_type: str  # "Jahresbericht" | "Halbjahresbericht" | "Annual Report"
    chunk_idx: int
    content: str
    embedding: list[float]  # must be EMBEDDING_DIM=2048
    metadata: dict[str, Any]
    ingested_at: datetime

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()
