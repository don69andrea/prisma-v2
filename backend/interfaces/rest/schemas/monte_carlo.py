"""Pydantic-Schemas für Monte Carlo API."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class HoldingWeightRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=12)
    weight: float = Field(..., gt=0.0, le=1.0)


class MonteCarloRequest(BaseModel):
    holdings: list[HoldingWeightRequest] = Field(..., min_length=1, max_length=10)
    monthly_contribution: float = Field(588.0, ge=0.0, le=10_000.0)
    years: int = Field(30, ge=1, le=40)
    initial_value: float = Field(0.0, ge=0.0)
    n_simulations: int = Field(10_000, ge=100, le=50_000)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> MonteCarloRequest:
        total = sum(h.weight for h in self.holdings)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Gewichte müssen 1.0 ergeben (ist {total:.3f})")
        return self


class MonteCarloResponse(BaseModel):
    p5: list[float]
    p50: list[float]
    p95: list[float]
    final_distribution: list[float]
    prob_positive_return: float
    prob_500k: float
    contribution_total: float
    months: int
