"""SQLAlchemy-Implementierung des StockRepository-Ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.stock import Stock
from backend.domain.repositories.stock_repository import StockRepository
from backend.infrastructure.persistence.models.stock import StockORM


class SQLAStockRepository(StockRepository):
    """Liest und schreibt Stock-Entitäten via AsyncSession in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, limit: int, offset: int) -> list[Stock]:
        """Paginierte Abfrage aller Stocks, alphabetisch nach Ticker sortiert."""
        stmt = select(StockORM).order_by(StockORM.ticker).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_domain(row) for row in rows]

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        """Sucht einen Stock anhand seines Ticker-Symbols (case-insensitive)."""
        stmt = select(StockORM).where(StockORM.ticker == ticker.upper())
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def get(self, stock_id: UUID) -> Stock | None:
        """Sucht einen Stock anhand seiner UUID."""
        orm = await self._session.get(StockORM, stock_id)
        return self._to_domain(orm) if orm else None

    @staticmethod
    def _to_domain(orm: StockORM) -> Stock:
        """Mapped ein ORM-Objekt auf die Domain-Entity — keine bidirektionale Kopplung."""
        return Stock(
            id=orm.id,
            ticker=orm.ticker,
            name=orm.name,
            isin=orm.isin,
            sector=orm.sector,
            country=orm.country,
            currency=orm.currency,
        )
