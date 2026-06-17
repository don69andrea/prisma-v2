"""SQLAlchemy ORM-Modell für die ranking_runs-Tabelle."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class RankingRunORM(Base):
    __tablename__ = "ranking_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("universes.id"), nullable=False
    )
    # WeightConfig als JSONB: {"quality_classic": 0.20, "alpha": 0.20, ...}
    weight_config: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Berechnungsergebnisse als JSONB-Array, nullable bis run completed
    results: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True, default=None)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
