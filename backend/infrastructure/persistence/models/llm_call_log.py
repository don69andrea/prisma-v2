"""SQLAlchemy ORM-Modell für die llm_call_log-Audit-Tabelle.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §3.

Eine Zeile pro LLM-Call (Anthropic + Voyage). Cost-Tracking,
Cap-Check-Queries und Admin-Endpoint lesen aus dieser Tabelle.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class LLMCallLogORM(Base):
    """Audit-Eintrag für einen einzelnen LLM-API-Call."""

    __tablename__ = "llm_call_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # 'anthropic' | 'voyage'
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # z.B. 'claude-sonnet-4-6' | 'voyage-3-large'
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    # z.B. 'narrative_engine' | 'rag_ingestion' — semantischer Tag des Aufrufers
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    # NUMERIC(10, 6) — Decimal-präzise Kosten in USD (CLAUDE.md-Geld-Regel)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    # Anthropic-internal request ID, optional für Debugging
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    __table_args__ = (
        # Cap-Check-Query nutzt created_at-Range; Index ist Performance-kritisch.
        Index("ix_llm_call_log_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<LLMCallLogORM model={self.model!r} feature={self.feature!r} "
            f"cost_usd={self.cost_usd}>"
        )
