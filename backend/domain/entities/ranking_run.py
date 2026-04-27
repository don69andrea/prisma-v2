"""RankingRun-Aggregate — repräsentiert einen vollständigen Ranking-Durchlauf."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from backend.domain.entities.universe import WeightConfig

RankingRunStatus = Literal["pending", "running", "completed", "failed"]


class RankingRun(BaseModel):
    """Aggregate-Root für einen Ranking-Lauf über ein Universe."""

    model_config = {"frozen": True}

    id: UUID
    created_at: datetime
    universe_id: UUID
    weight_config: WeightConfig
    status: RankingRunStatus = "pending"
