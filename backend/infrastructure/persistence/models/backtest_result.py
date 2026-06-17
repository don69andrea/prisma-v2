"""SQLAlchemy ORM-Modell für die backtest_results-Tabelle."""

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class BacktestResultORM(Base):
    __tablename__ = "backtest_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    top_n: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    benchmark_ticker: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    # Metrics and series stored as JSONB — avoids wide column tables
    prisma_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    universe_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    benchmark_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    series: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
