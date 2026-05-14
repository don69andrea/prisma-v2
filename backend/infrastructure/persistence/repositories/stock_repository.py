"""SQLAlchemy-Implementierung des StockRepository-Ports."""

from __future__ import annotations

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

    async def list_by_ids(self, stock_ids: list[UUID]) -> list[Stock]:
        """Bulk-Lookup via `id IN (...)` — 1 Roundtrip statt N."""
        if not stock_ids:
            return []
        stmt = select(StockORM).where(StockORM.id.in_(stock_ids))
        result = await self._session.execute(stmt)
        return [self._to_domain(r) for r in result.scalars().all()]

    async def list_by_tickers(self, tickers: list[str]) -> list[Stock]:
        """Bulk-Lookup via `ticker IN (...)` — case-insensitive."""
        if not tickers:
            return []
        upper = [t.upper() for t in tickers]
        stmt = select(StockORM).where(StockORM.ticker.in_(upper))
        result = await self._session.execute(stmt)
        return [self._to_domain(r) for r in result.scalars().all()]

    # `list` ist am Ende — siehe Hinweis im Port: Methoden-Name shadowed
    # builtin `list` in der Klassen-Scope, was nachfolgende `list[X]`-
    # Annotationen broeselt.
    async def list(self, limit: int, offset: int) -> list[Stock]:
        """Paginierte Abfrage aller Stocks, alphabetisch nach Ticker sortiert."""
        stmt = select(StockORM).order_by(StockORM.ticker).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_domain(row) for row in rows]

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
