"""ORM model for signal_outcomes table (V4-6 SignalEvaluationJob)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class SignalOutcomeORM(Base):
    __tablename__ = "signal_outcomes"

    coin_id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    signal_date: Mapped[date] = mapped_column(sa.Date(), primary_key=True)
    horizon: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    action: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    size_factor: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    pred_vol: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    realized_fwd_return: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    model_version: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        default=lambda: datetime.now(tz=UTC),
    )
