"""3a-Eligibility-Ergebnis — Wert-Objekt für die Säule-3a-Eignung."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EligibilityReason(StrEnum):
    """Ablehnungsgrund für 3a-Eignung gemäss BVV2/FINMA."""

    EXCHANGE_NOT_RECOGNIZED = "exchange_not_recognized"
    MARKET_CAP_TOO_LOW = "market_cap_too_low"


@dataclass(frozen=True)
class EligibilityResult:
    """Binäres 3a-Eignungs-Urteil mit Begründungen.

    `reasons` ist leer wenn `eligible=True`.
    """

    ticker: str
    eligible: bool
    reasons: tuple[EligibilityReason, ...]
