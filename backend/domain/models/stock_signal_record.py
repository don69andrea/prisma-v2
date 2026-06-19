from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class StockSignalRecord:
    id: str
    ticker: str
    snapshot_date: date
    signal: str
    weighted_score: float
    quant_score: float
    ml_score: float
    macro_score: float
    confidence: float
    is_3a_eligible: bool
    ml_is_fallback: bool = False
    created_at: datetime | None = None
