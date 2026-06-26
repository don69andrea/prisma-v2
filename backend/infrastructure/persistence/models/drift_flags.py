"""ORM model for drift_flags (V4-6 DriftMonitor)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class DriftFlagORM(Base):
    __tablename__ = "drift_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    coin: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    flagged_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        default=lambda: datetime.now(tz=UTC),
    )
    metric_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    live_value: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    expected_value: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    pct_deviation: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=True
    )
    alert_sent: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False
    )
