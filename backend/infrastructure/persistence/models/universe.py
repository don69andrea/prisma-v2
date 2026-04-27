"""SQLAlchemy ORM-Modell für die universes-Tabelle."""

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class UniverseORM(Base):
    __tablename__ = "universes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    tickers: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False)

    __table_args__ = (Index("ix_universes_name", "name", unique=True),)
