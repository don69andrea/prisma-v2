"""ORM-Mapping fuer memo_batch_jobs Tabelle."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class MemoBatchJobORM(Base):
    """SQLA-Mapping fuer memo_batch_jobs.

    UPSERT via pg_insert.on_conflict_do_update mit id und created_at
    als Lifecycle-Marker (nicht im set_).
    """

    __tablename__ = "memo_batch_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    model_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ranking_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    top_n: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failed_stock_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    expected_stock_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("top_n BETWEEN 1 AND 100", name="top_n"),
        CheckConstraint("language IN ('de', 'en')", name="language"),
        CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'partial', 'failed')",
            name="status",
        ),
        Index("ix_memo_batch_jobs_model_run_id", "model_run_id"),
    )
