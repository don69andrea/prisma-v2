"""Pydantic-Schema für 3a-Eligibility-Response."""

from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.eligibility_result import EligibilityReason


class EligibilityResponse(BaseModel):
    """Response-Schema für GET /api/v1/stocks/{ticker}/3a-eligibility."""

    ticker: str
    eligible: bool
    reasons: list[EligibilityReason]
