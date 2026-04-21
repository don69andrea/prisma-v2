"""FastAPI Dependency-Injection-Kette: Session → Repository → Service."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.stock_service import StockService
from backend.domain.repositories.stock_repository import StockRepository
from backend.infrastructure.persistence.repositories.stock_repository import (
    SQLAStockRepository,
)
from backend.infrastructure.persistence.session import get_async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Liefert eine AsyncSession für den aktuellen Request-Scope."""
    async for session in get_async_session():
        yield session


async def get_stock_repository(
    session: AsyncSession = Depends(get_session),
) -> StockRepository:
    """Instanziiert den SQLAlchemy-Adapter mit der aktuellen Session."""
    return SQLAStockRepository(session=session)


async def get_stock_service(
    repository: StockRepository = Depends(get_stock_repository),
) -> StockService:
    """Erstellt einen StockService mit dem injizierten Repository."""
    return StockService(repository=repository)
