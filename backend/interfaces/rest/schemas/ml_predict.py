"""Pydantic-Schemas für ML Prediction API."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MLPredictRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Swiss ticker (z.B. NESN)")


class SHAPEntryResponse(BaseModel):
    feature: str
    shap_value: float
    feature_value: float
    label: str


class MLPredictResponse(BaseModel):
    ticker: str
    snapshot_date: date
    predicted_class: int = Field(..., ge=0, le=2)
    signal: str = Field(..., description="UNDERPERFORM | NEUTRAL | OUTPERFORM")
    prob_bottom: float = Field(..., ge=0.0, le=1.0)
    prob_mid: float = Field(..., ge=0.0, le=1.0)
    prob_top: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_type: str
    features: dict[str, float]
    shap_values: list[SHAPEntryResponse] = Field(default_factory=list)
    shap_expected_value: float = 0.0
