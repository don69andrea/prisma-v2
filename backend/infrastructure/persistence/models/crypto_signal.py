"""SQLAlchemy ORM-Modell für die crypto_signals-Tabelle."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class CryptoSignalORM(Base):
    __tablename__ = "crypto_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    signal: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    price_chf: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    fear_greed_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[str | None] = mapped_column(String(10), nullable=True)
    volatility_30d_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_patterns: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    pattern_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_crypto_signals_ticker_date", "ticker", "created_at"),)
