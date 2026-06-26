"""ORM model for live_performance_metrics (V4-6)."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class LivePerformanceMetricORM(Base):
    __tablename__ = "live_performance_metrics"

    id: Mapped[int] = mapped_column(
        sa.Integer(), primary_key=True, autoincrement=True
    )
    coin_id: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        default=lambda: datetime.now(tz=UTC),
    )
    window_days: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    n_signals: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    hit_rate: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    live_sharpe: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    live_calmar: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    vol_mae: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
