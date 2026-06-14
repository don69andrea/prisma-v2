"""InvestorProfile-Entity — Nutzerprofil für die personalisierte Discovery Engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class InvestorProfile(BaseModel):
    """Repräsentiert das Investorenprofil eines Nutzers für die personalisierte Titelauswahl.

    session_id verknüpft das Profil mit der anonymen Frontend-Session.
    confidence_score steuert, ob weitere Fragen gestellt werden (< 0.6 → mehr Fragen).
    """

    id: UUID = Field(default_factory=uuid4)
    session_id: str  # Frontend-Session-Identifier / Redis-Key

    # Turn 1 — Beruf & Wissensstand
    profession: str | None = None
    financial_knowledge: Literal["low", "medium", "high"] = "low"
    sector_hint: str | None = None  # aus Beruf-Klassifikation (Turn 1), z.B. "tech", "pharma"

    # Turn 2 — Ziel
    investment_goal: Literal[
        "housing",
        "retirement",
        "freedom",
        "beat_savings",
        "other",
    ] = "beat_savings"

    # Turn 3 — Zeithorizont + Risikoprofil
    time_horizon: Literal["short", "medium", "long"] = "medium"
    risk_profile: Literal["conservative", "moderate", "aggressive"] = "moderate"

    # Turn 4 — Brand-Mapping
    sector_affinity: list[str] = Field(default_factory=list)
    known_tickers: list[str] = Field(default_factory=list)

    # Turn 5 — Anlagebetrag (Grössenordnung)
    investment_amount: Literal["under_10k", "10k_100k", "over_100k"] = "10k_100k"

    # Turn 6 — ESG-Präferenz
    esg_preference: Literal["yes", "no", "indifferent"] = "indifferent"

    # Turn 7 — Rendite-Präferenz: Dividenden vs. Wachstum
    income_preference: Literal["dividends", "growth", "balanced"] = "balanced"

    # Klassifikations-Zustand
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    onboarding_complete: bool = False

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_onboarding_consistency(self) -> "InvestorProfile":
        """Wenn Onboarding abgeschlossen ist, muss ein explizites Risikoprofil gesetzt sein."""
        if self.onboarding_complete and self.risk_profile == "moderate":
            raise ValueError(
                "onboarding_complete=True erfordert ein explizit gesetztes risk_profile "
                "(nicht den Default-Wert 'moderate')."
            )
        return self

    @property
    def risk_label(self) -> str:
        labels: dict[str, str] = {
            "conservative": "Konservativ — Stabilität über Wachstum",
            "moderate": "Ausgewogen — Stabilität und Wachstum",
            "aggressive": "Wachstumsorientiert — Rendite über Stabilität",
        }
        return labels[self.risk_profile]
