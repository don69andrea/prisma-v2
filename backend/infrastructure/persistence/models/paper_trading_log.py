"""ORM model for paper_trading_log (V4-6b, append-only)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class PaperTradingLogORM(Base):
    __tablename__ = "paper_trading_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    coin: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    signal_date: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    size_factor: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    pred_vol: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    realized_fwd_return: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    written_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        default=lambda: datetime.now(tz=UTC),
    )
