"""Pydantic-Schema für 3a-Eligibility-Response."""

from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.eligibility_result import EligibilityReason

# Menschenlesbare Beschreibungen der Ablehnungsgründe (DE)
_REASON_LABELS: dict[EligibilityReason, str] = {
    EligibilityReason.EXCHANGE_NOT_RECOGNIZED: (
        "Börse nicht anerkannt — nur SIX Swiss Exchange (XSWX) ist für 3a zugelassen"
    ),
    EligibilityReason.MARKET_CAP_TOO_LOW: (
        "Marktkapitalisierung unter CHF 100 Mio. — Mindestliquidität gemäss BVV2 Art. 53 nicht erfüllt"
    ),
}

_ELIGIBLE_REASON = "Erfüllt BVV2 Art. 53 Kriterien (XSWX-Börse, Marktkapitalisierung ≥ CHF 100 Mio.)"


class EligibilityResponse(BaseModel):
    """Response-Schema für GET /api/v1/stocks/{ticker}/3a-eligibility."""

    ticker: str
    eligible: bool
    reasons: list[EligibilityReason]
    reason: str
