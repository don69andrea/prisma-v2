"""SQLAlchemy ORM-Modell für die decision_audit_log-Tabelle."""

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class DecisionAuditLogORM(Base):
    __tablename__ = "decision_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(sa.String(20), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    weighted_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    quant_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    ml_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    macro_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    is_3a_eligible: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    explanation_de: Mapped[str] = mapped_column(sa.Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
