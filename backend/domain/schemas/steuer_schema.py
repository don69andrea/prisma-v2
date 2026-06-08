"""Pydantic-Output-Schema für den Steuer-Implikations-Agenten.

Alle LLM-Outputs werden gegen dieses Schema validiert (AGENTS.md-Pflicht).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

_DISCLAIMER = (
    "⚠️ Diese Einschätzung dient ausschliesslich zu Informationszwecken "
    "und stellt keine Steuerberatung dar. Für verbindliche Steuerauskünfte "
    "wenden Sie sich an eine zugelassene Steuerfachperson oder das zuständige "
    "kantonale Steueramt. Steuergesetze ändern sich — prüfen Sie die Aktualität "
    "der Angaben."
)


class SteuerEinschätzung(BaseModel):
    """Strukturierte Steuereinschätzung für eine Schweizer 3a-/Vorsorge-Position."""

    ticker: str = Field(..., min_length=1, max_length=10)
    anlegerprofil: Literal["privatperson", "vorsorge_3a", "vorsorge_2a", "institution"]
    halteperiode_jahre: int = Field(..., ge=1, le=50)

    steuerarten: list[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="Relevante Steuerarten (z.B. Verrechnungssteuer, Einkommenssteuer)",
    )
    pflichten: list[str] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Steuerliche Pflichten und Deklarationspflichten",
    )
    hinweise: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Wichtige Hinweise und Besonderheiten",
    )
    quellen: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Quellenangaben (ESTV-Kreisschreiben, BVV2-Artikel etc.)",
    )

    disclaimer: str = Field(default=_DISCLAIMER)
    generated_at: datetime
    model_version: str = Field(..., min_length=1, max_length=64)


PFLICHT_DISCLAIMER = _DISCLAIMER
