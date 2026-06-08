"""Pydantic-Schemas für ML Prediction API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MLPredictRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Swiss ticker (z.B. NESN)")


class MLPredictResponse(BaseModel):
    ticker: str
    snapshot_date: date
    predicted_class: int = Field(..., ge=0, le=2, description="0=Bottom, 1=Mid, 2=Top Quartil")
    signal: str = Field(..., description="UNDERPERFORM | NEUTRAL | OUTPERFORM")
    prob_bottom: float = Field(..., ge=0.0, le=1.0)
    prob_mid: float = Field(..., ge=0.0, le=1.0)
    prob_top: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0, description="max(probabilities)")
    model_type: str
    features: dict[str, float] = Field(description="Feature-Werte die zur Vorhersage geführt haben")
