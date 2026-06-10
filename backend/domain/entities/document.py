"""Document-Entity — repraesentiert ein indiziertes SEC-Filing (10-K / 10-Q).

Frozen-Dataclass mit __post_init__-Validation (CLAUDE.md §"Datumshandling
ohne Timezone vermeiden"). `raw_text_hash` ist Slice-1 immer None;
Slice 2 fuellt es nach Text-Extraktion.
"""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

_VALID_DOC_TYPES = frozenset({"10-K", "10-Q", "ESTV", "BVV2"})


@dataclass(frozen=True)
class Document:
    id: UUID
    ticker: str
    doc_type: str
    filing_date: date
    url: str
    raw_text_hash: str | None
    ingested_at: datetime

    def __post_init__(self) -> None:
        if self.doc_type not in _VALID_DOC_TYPES:
            raise ValueError(
                f"doc_type must be one of {sorted(_VALID_DOC_TYPES)}, got {self.doc_type!r}"
            )
        if not self.url:
            raise ValueError("url must be non-empty")
        if self.ingested_at.tzinfo is None:
            raise ValueError("ingested_at must be timezone-aware (UTC)")
