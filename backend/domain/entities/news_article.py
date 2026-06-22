"""NewsArticle-Entity — ein CH-Finanzartikel aus RSS-Feed (NZZ / SRF)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

_VALID_SOURCES = frozenset({"NZZ", "SRF", "CRYPTOPANIC"})


@dataclass(frozen=True)
class NewsArticle:
    id: UUID
    url: str
    url_hash: str  # SHA-256 hex — Deduplizierungsschlüssel
    title: str
    content: str
    published_at: datetime | None
    source: str  # "NZZ" | "SRF"
    tickers: tuple[str, ...]  # NER-erkannte Swiss Tickers
    ingested_at: datetime

    def __post_init__(self) -> None:
        if self.source not in _VALID_SOURCES:
            raise ValueError(f"source must be one of {sorted(_VALID_SOURCES)}, got {self.source!r}")
        if not self.url:
            raise ValueError("url must be non-empty")
        if not self.title:
            raise ValueError("title must be non-empty")
        expected_hash = hashlib.sha256(self.url.encode()).hexdigest()
        if self.url_hash != expected_hash:
            raise ValueError("url_hash does not match SHA-256 of url")
        if self.ingested_at.tzinfo is None:
            raise ValueError("ingested_at must be timezone-aware (UTC)")
        if self.published_at is not None and self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware when set")

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()
