"""SQLAlchemy ORM model for the hitl_confirmations table (append-only, HITL audit log).

Records every human-in-the-loop decision (proceed/abort) against an agent audit trail entry.
APPEND-ONLY: no UPDATE, no DELETE — this is a pure decision log, not a state store.
UI is read-only; this endpoint ONLY logs decisions, never triggers trades.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class HitlConfirmationORM(Base):
    """Immutable record of a human-in-the-loop confirm/abort decision.

    APPEND-ONLY: No UPDATE, no DELETE — ever.
    Multiple rows for the same audit_trail_id are intentional and allowed
    (a user may re-confirm or re-abort the same audit entry).

    audit_trail_id is a soft foreign key to agent_audit_trail.id —
    no FK constraint to avoid cross-migration dependency issues.
    """

    __tablename__ = "hitl_confirmations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    audit_trail_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    coin: Mapped[str] = mapped_column(sa.String(), nullable=False)
    decision: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # "proceed" | "abort"
    decided_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        default=lambda: datetime.now(tz=UTC),
    )
