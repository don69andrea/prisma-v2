"""SQLAlchemy ORM-Modell für die stocks-Tabelle."""

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class StockORM(Base):
    """Persistenzdarstellung einer Stock-Entity in PostgreSQL."""

    __tablename__ = "stocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # ISO 4217, immer 3 Zeichen
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    __table_args__ = (
        # Unique-Index für schnelle Ticker-Lookups; stellt DB-seitige Eindeutigkeit sicher.
        Index("ix_stocks_ticker", "ticker", unique=True),
    )

    def __repr__(self) -> str:
        return f"<StockORM ticker={self.ticker!r} name={self.name!r}>"
