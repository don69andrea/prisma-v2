"""Pydantic-Schemas für den Admin-Cost-Summary-Endpoint (GET /api/v1/admin/costs).

Konvertiert das Application-Layer-CostSummary (mit Decimal-Feldern) in
JSON-serialisierbare Pydantic-Modelle mit float. Spezifiziert in §9.
"""

from datetime import datetime

from pydantic import BaseModel

from backend.domain.cost_summary import CostSummary


class ModelBreakdownResponse(BaseModel):
    model: str
    calls: int
    cost_usd: float


class FeatureBreakdownResponse(BaseModel):
    feature: str
    calls: int
    cost_usd: float


class CallEntryResponse(BaseModel):
    created_at: datetime
    model: str
    feature: str
    cost_usd: float


class CostSummaryResponse(BaseModel):
    month: str
    cap_usd: float
    current_usd: float
    remaining_usd: float
    by_model: list[ModelBreakdownResponse]
    by_feature: list[FeatureBreakdownResponse]
    last_calls: list[CallEntryResponse]

    @classmethod
    def from_cost_summary(cls, summary: CostSummary) -> "CostSummaryResponse":
        """Konvertiert das Application-Layer-CostSummary in die API-Response."""
        return cls(
            month=summary.month,
            cap_usd=float(summary.cap_usd),
            current_usd=float(summary.current_usd),
            remaining_usd=float(summary.remaining_usd),
            by_model=[
                ModelBreakdownResponse(
                    model=b.model,
                    calls=b.calls,
                    cost_usd=float(b.cost_usd),
                )
                for b in summary.by_model
            ],
            by_feature=[
                FeatureBreakdownResponse(
                    feature=b.feature,
                    calls=b.calls,
                    cost_usd=float(b.cost_usd),
                )
                for b in summary.by_feature
            ],
            last_calls=[
                CallEntryResponse(
                    created_at=c.created_at,
                    model=c.model,
                    feature=c.feature,
                    cost_usd=float(c.cost_usd),
                )
                for c in summary.last_calls
            ],
        )
