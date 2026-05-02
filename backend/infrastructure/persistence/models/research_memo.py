"""SQLAlchemy ORM-Modell für research_memos (Foundation-Spec §4)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class ResearchMemoORM(Base):
    """Persistiertes Research-Memo zu einem Stock innerhalb eines Ranking-Runs."""

    __tablename__ = "research_memos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ranking_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="de",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    one_liner: Mapped[str] = mapped_column(String(150), nullable=False)
    ranking_interpretation: Mapped[str] = mapped_column(String(600), nullable=False)
    sweet_spot: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sweet_spot_explanation: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contradictions: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    key_strengths: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    key_risks: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "model_run_id",
            "language",
            name="uq_research_memos_stock_run_lang",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="confidence",
        ),
        Index("ix_research_memos_model_run_id", "model_run_id"),
    )
