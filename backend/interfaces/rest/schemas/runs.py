"""Request/Response-Schemas für /api/v1/runs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from backend.domain.entities.ranking_run import RankingRun, RankingRunStatus
from backend.domain.entities.universe import VALID_MODELS, WeightConfig

_WEIGHT_TOLERANCE = 1e-6


class PostRunRequest(BaseModel):
    universe_id: UUID
    weight_config: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_weights(self) -> "PostRunRequest":
        if self.weight_config is None:
            return self
        unknown = set(self.weight_config.keys()) - VALID_MODELS
        if unknown:
            raise ValueError(f"Unbekannte Modell-Namen: {unknown}")
        total = sum(self.weight_config.values())
        if abs(total - 1.0) > _WEIGHT_TOLERANCE:
            raise ValueError(f"Gewichte müssen 1.0 ergeben, nicht {total:.6f}")
        return self

    def to_weight_config(self) -> WeightConfig | None:
        if self.weight_config is None:
            return None
        return WeightConfig(weights=self.weight_config)


class RunResponse(BaseModel):
    id: UUID
    status: RankingRunStatus
    universe_id: UUID
    created_at: datetime

    @classmethod
    def from_domain(cls, run: RankingRun) -> "RunResponse":
        return cls(
            id=run.id,
            status=run.status,
            universe_id=run.universe_id,
            created_at=run.created_at,
        )


class RankingItem(BaseModel):
    ticker: str
    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool
    per_model_ranks: dict[str, int | None]
