"""Pydantic-Schemas für V4-6 Operations & Learning Loop API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaperLogEntrySchema(BaseModel):
    id: uuid.UUID
    coin: str
    signal_date: date
    action: Literal["BUY", "HOLD", "SELL"]
    size_factor: float = Field(ge=0.0, le=1.5)
    confidence: float = Field(ge=0.0, le=1.0)
    pred_vol: float | None
    realized_fwd_return: float | None
    written_at: datetime


class PaperLogResponse(BaseModel):
    entries: list[PaperLogEntrySchema]
    total: int
    disclaimer: str = "Out-of-sample paper log. Entscheidungsunterstützung, kein Anlagerat."
