"""NewsRetrievalResult — Ähnlichkeits-Treffer aus pgvector-Suche über News-Chunks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class NewsRetrievalResult:
    chunk_id: UUID
    news_document_id: UUID
    chunk_idx: int
    content: str
    similarity: float
    title: str
    url: str  # article URL — populated from nd.url in find_nearest() (B-02)
    source: str
    tickers: tuple[str, ...]
    published_at: datetime | None
    metadata: dict[str, Any]
