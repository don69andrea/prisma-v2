# backend/infrastructure/persistence/models/stock.py
"""SQLAlchemy ORM-Modell für die stocks-Tabelle."""

import uuid
from decimal import Decimal

from sqlalchemy import Index, Numeric, String
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
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Swiss Market fields (nullable for non-Swiss stocks)
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)
    market_cap_chf: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    __table_args__ = (
        Index("ix_stocks_ticker", "ticker", unique=True),
    )

    def __repr__(self) -> str:
        return f"<StockORM ticker={self.ticker!r} name={self.name!r}>"
