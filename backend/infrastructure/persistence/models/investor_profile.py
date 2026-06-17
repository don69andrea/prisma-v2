"""SQLAlchemy ORM-Modell für die investor_profiles-Tabelle."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class InvestorProfileORM(Base):
    __tablename__ = "investor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    profession: Mapped[str | None] = mapped_column(String(255), nullable=True)
    financial_knowledge: Mapped[str] = mapped_column(String(10), nullable=False, default="low")
    investment_goal: Mapped[str] = mapped_column(String(20), nullable=False, default="beat_savings")
    time_horizon: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    sector_hint: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sector_affinity: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, default=list
    )
    known_tickers: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list)
    investment_amount: Mapped[str] = mapped_column(String(20), nullable=False, default="10k_100k")
    esg_preference: Mapped[str] = mapped_column(String(15), nullable=False, default="indifferent")
    income_preference: Mapped[str] = mapped_column(String(15), nullable=False, default="balanced")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
