"""Pydantic-Schemas für Macro Intelligence API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MacroContextResponse(BaseModel):
    leitzins: float = Field(..., description="SNB-Leitzins in %")
    chf_eur: float = Field(..., description="CHF pro EUR")
    inflation_ch: float | None = Field(None, description="Schweizer Inflationsrate YoY in %")
    pmi_ch: float | None = Field(None, description="Schweizer PMI")
    snapshot_date: date
    climate: str = Field(..., description="EXPANSIV | NEUTRAL | RESTRIKTIV")
    narrative_de: str
    narrative_en: str


class MacroScoreResponse(BaseModel):
    """Ticker-spezifischer Makro-Score mit RAG-Integration."""

    ticker: str = Field(..., description="SIX-Ticker-Symbol (z.B. 'NESN.SW')")
    score: float = Field(..., ge=0.0, le=100.0, description="Makro-Score 0–100")
    leitzins: float = Field(..., description="SNB-Leitzins in %")
    chf_eur: float = Field(..., description="CHF pro EUR")
    climate: str = Field(..., description="EXPANSIV | NEUTRAL | RESTRIKTIV")
    rag_context_used: bool = Field(
        ..., description="True wenn RAG-Kontext (Makro-News) in die Bewertung eingeflossen ist"
    )
