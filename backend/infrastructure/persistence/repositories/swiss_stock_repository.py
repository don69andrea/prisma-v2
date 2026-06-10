# backend/infrastructure/persistence/repositories/swiss_stock_repository.py
"""SQLAlchemy-Implementierung des SwissStockRepository-Ports."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.infrastructure.persistence.models.stock import StockORM


class SQLASwissStockRepository(SwissStockRepository):
    """Liest und schreibt SwissStock-Entitäten via AsyncSession in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticker(self, ticker: str) -> SwissStock | None:
        stmt = (
            select(StockORM)
            .where(StockORM.ticker == ticker.upper())
            .where(StockORM.exchange.isnot(None))
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def list_by_exchange(
        self,
        exchange: Literal["XSWX"] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SwissStock]:
        stmt = select(StockORM).where(StockORM.exchange.isnot(None))
        if exchange is not None:
            stmt = stmt.where(StockORM.exchange == exchange)
        stmt = stmt.order_by(StockORM.ticker).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def upsert_batch(self, stocks: list[SwissStock]) -> int:
        """Idempotentes INSERT … ON CONFLICT (ticker) DO UPDATE."""
        if not stocks:
            return 0
        values = [
            {
                "ticker": s.ticker,
                "isin": s.isin,
                "name": s.name,
                "sector": s.sector,
                "country": "CH",
                "currency": s.currency,
                "exchange": s.exchange,
                "market_cap_chf": s.market_cap_chf,
            }
            for s in stocks
        ]
        stmt = pg_insert(StockORM).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker"],
            set_={
                "isin": stmt.excluded.isin,
                "name": stmt.excluded.name,
                "sector": stmt.excluded.sector,
                "exchange": stmt.excluded.exchange,
                "market_cap_chf": stmt.excluded.market_cap_chf,
            },
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined,no-any-return]

    @staticmethod
    def _to_domain(orm: StockORM) -> SwissStock:
        if orm.isin is None:
            raise ValueError(
                f"StockORM {orm.ticker!r} has exchange set but isin=NULL — data invariant violation"
            )
        return SwissStock(
            id=orm.id,
            ticker=orm.ticker,
            isin=orm.isin,
            name=orm.name,
            exchange=orm.exchange,  # type: ignore[arg-type]
            sector=orm.sector,
            market_cap_chf=Decimal(str(orm.market_cap_chf)) if orm.market_cap_chf else None,
        )
