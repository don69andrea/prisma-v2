"""Pydantic-Schemas für Alert API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AlertCreateRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    trigger_type: Literal["SIGNAL_CHANGE", "PRICE_CHANGE"]
    threshold: float = Field(default=5.0, ge=0.0, le=100.0)
    channel: Literal["EMAIL", "WEBHOOK"]
    target: str = Field(..., min_length=1, max_length=255)

    @field_validator("ticker")
    @classmethod
    def ticker_upper(cls, v: str) -> str:
        return v.upper()


class AlertResponse(BaseModel):
    id: UUID
    ticker: str
    trigger_type: str
    threshold: float
    channel: str
    target: str
    is_active: bool
    created_at: datetime
    last_triggered_at: datetime | None
    last_signal: str | None
    baseline_price: float | None


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
    total: int
