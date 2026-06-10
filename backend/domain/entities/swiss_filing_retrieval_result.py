"""Domain-Entity: Ergebnis einer Swiss-RAG-Suche."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SwissFilingRetrievalResult:
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
    metadata: dict[str, Any]
