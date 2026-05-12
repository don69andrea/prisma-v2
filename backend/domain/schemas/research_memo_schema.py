"""Pydantic-Schemas für externe Verträge (LLM-Output etc.)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.domain.entities.research_memo import ContradictionItem


class ResearchMemoSchema(BaseModel):
    """LLM-Output-Vertrag — was wir von Claude erwarten.

    Foundation-Spec §5.2 wortgetreu (siehe docs/specs/2026-04-30-narrative-engine-foundation.md). Wird im Service zu ResearchMemo (Entity)
    gemappt — Mapping kommt in Folge-PR.
    """

    ticker: str = Field(..., min_length=1, max_length=10)
    total_rank: int = Field(..., ge=1)

    one_liner: str = Field(..., min_length=10, max_length=150)
    ranking_interpretation: str = Field(..., min_length=100, max_length=1000)
    sweet_spot: bool
    sweet_spot_explanation: str | None = Field(None, max_length=300)
    contradictions: list[ContradictionItem] = Field(default_factory=list, max_length=3)
    key_strengths: list[str] = Field(..., min_length=1, max_length=5)
    key_risks: list[str] = Field(..., min_length=1, max_length=5)
    confidence: Literal["low", "medium", "high"]

    generated_at: datetime
    model_version: str = Field(..., min_length=1, max_length=64)
