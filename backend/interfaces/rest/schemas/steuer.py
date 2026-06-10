"""Pydantic-REST-Schemas für den Steuer-Implikations-Agenten."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SteuerAnfrageRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    anlegerprofil: Literal["privatperson", "vorsorge_3a", "vorsorge_2a", "institution"] = (
        "vorsorge_3a"
    )
    halteperiode_jahre: int = Field(default=30, ge=1, le=50)


class SteuerEinschätzungResponse(BaseModel):
    ticker: str
    anlegerprofil: str
    halteperiode_jahre: int
    steuerarten: list[str]
    pflichten: list[str]
    hinweise: list[str]
    quellen: list[str]
    disclaimer: str
    generated_at: datetime
    model_version: str
