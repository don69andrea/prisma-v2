"""Integration-Tests fuer SQLAStockRepository.get(stock_id)."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.stock import Stock
from backend.infrastructure.persistence.models.stock import StockORM
from backend.infrastructure.persistence.repositories.stock_repository import (
    SQLAStockRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def seeded_stock(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, str]:
    """Persistiere einen Stock und gib (id, ticker) zurueck."""
    stock_id = uuid4()
    async with session_factory() as session:
        session.add(
            StockORM(
                id=stock_id,
                ticker="NESN",
                name="Nestle SA",
                isin="CH0038863350",
                sector="Consumer Staples",
                country="CH",
                currency="CHF",
            )
        )
        await session.commit()
    return stock_id, "NESN"


async def test_get_returns_stock_when_found(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_stock: tuple[UUID, str],
) -> None:
    stock_id, _ticker = seeded_stock
    async with session_factory() as session:
        repo = SQLAStockRepository(session=session)
        stock = await repo.get(stock_id)

    assert stock is not None
    assert isinstance(stock, Stock)
    assert stock.id == stock_id
    assert stock.ticker == "NESN"


async def test_get_returns_none_when_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SQLAStockRepository(session=session)
        stock = await repo.get(uuid4())

    assert stock is None
