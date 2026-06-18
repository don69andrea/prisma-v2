"""Pydantic-Output-Schemas für Multi-Agent-Features.

Enthält Schemas für CointelligenceAgent und weitere Multi-Agent-Ausgaben.
Alle LLM-Outputs werden gegen diese Schemas validiert (AGENTS.md-Pflicht).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

_DISCLAIMER = (
    "Kryptowährungen sind hochspekulative Anlagen mit erheblichem Verlustrisiko. "
    "Diese Analyse ist keine Anlageberatung. Nie mehr als 5–10% des freien Vermögens."
)


class CointelligenceReport(BaseModel):
    """Strukturierter Krypto-Analysebericht für Schweizer Privatanleger."""

    coin: Literal["BTC", "ETH"]
    price_chf: float = Field(..., ge=0.0, description="Aktueller Preis in CHF")
    mvrv_zone: Literal["UNDERBOUGHT", "FAIR", "EXPENSIVE", "EXTREME", "UNKNOWN"] = Field(
        ..., description="MVRV-Z-Score-Zone"
    )
    fear_greed: int = Field(..., ge=0, le=100, description="Fear & Greed Index (0=Angst, 100=Gier)")
    sharpe_crypto: float = Field(..., description="Sharpe Ratio Krypto (365d annualisiert)")
    sharpe_smi: float = Field(..., description="Sharpe Ratio SMI (365d annualisiert)")
    chf_usd_impact: str = Field(..., description="Einfluss des CHF/USD-Kurses auf den CHF-Preis")
    regime_signal: Literal["ACCUMULATE", "HOLD", "CAUTION", "AVOID"] = Field(
        ..., description="Investitionsempfehlung"
    )
    max_allocation_pct: float = Field(
        ..., ge=0.0, le=10.0, description="Maximal empfohlene Allokation in % des freien Vermögens"
    )
    reasoning: str = Field(..., min_length=1, description="Kurze Begründung (max 3 Sätze)")
    disclaimer: str = Field(default=_DISCLAIMER)
