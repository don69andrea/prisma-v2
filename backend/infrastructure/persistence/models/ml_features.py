"""SQLAlchemy-ORM-Modell für ml_features (Feature Store)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class MLFeatureORM(Base):
    __tablename__ = "ml_features"
    __table_args__ = (
        UniqueConstraint("ticker", "snapshot_date", name="uq_ml_features_ticker_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)

    # SwissQuantScorer-Komponenten
    quant_score: Mapped[float] = mapped_column(Float(), nullable=False)
    score_rendite: Mapped[float] = mapped_column(Float(), nullable=False)
    score_sicherheit: Mapped[float] = mapped_column(Float(), nullable=False)
    score_wachstum: Mapped[float] = mapped_column(Float(), nullable=False)
    score_substanz: Mapped[float] = mapped_column(Float(), nullable=False)

    # Technische Indikatoren
    return_12m: Mapped[float] = mapped_column(Float(), nullable=False)
    vol_30d: Mapped[float] = mapped_column(Float(), nullable=False)
    rsi_14: Mapped[float] = mapped_column(Float(), nullable=False)

    # Makro-Features
    snb_rate: Mapped[float] = mapped_column(Float(), nullable=False)
    chf_eur: Mapped[float] = mapped_column(Float(), nullable=False)

    # Trainingslabel (NULL für aktuelle Inferenz-Features)
    forward_return_12m: Mapped[float | None] = mapped_column(Float(), nullable=True)
    target_class: Mapped[int | None] = mapped_column(Integer(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
