"""Gemeinsame pytest-Fixtures für alle Test-Ebenen."""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.domain.entities.stock import Stock
from backend.domain.repositories.stock_repository import StockRepository
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_stock_repository


# ---------------------------------------------------------------------------
# In-Memory StockRepository für Integration-Tests ohne Datenbankverbindung
# ---------------------------------------------------------------------------


class InMemoryStockRepository(StockRepository):
    """Leichtgewichtige Test-Implementierung des StockRepository-Ports.

    Speichert Stocks in einer Python-Liste; keine I/O-Abhängigkeiten.
    """

    def __init__(self, stocks: list[Stock] | None = None) -> None:
        self._stocks: list[Stock] = stocks or []

    def add(self, stock: Stock) -> None:
        self._stocks.append(stock)

    async def list(self, limit: int, offset: int) -> list[Stock]:
        sorted_stocks = sorted(self._stocks, key=lambda s: s.ticker)
        return sorted_stocks[offset : offset + limit]

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        for stock in self._stocks:
            if stock.ticker == ticker.upper():
                return stock
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_sample_stocks() -> list[Stock]:
    return [
        Stock(
            id=uuid.uuid4(),
            ticker="AAPL",
            name="Apple Inc.",
            isin="US0378331005",
            sector="Technology",
            country="US",
            currency="USD",
        ),
        Stock(
            id=uuid.uuid4(),
            ticker="NESN",
            name="Nestlé S.A.",
            isin="CH0012221716",
            sector="Consumer Staples",
            country="CH",
            currency="CHF",
        ),
        Stock(
            id=uuid.uuid4(),
            ticker="NOVN",
            name="Novartis AG",
            isin="CH0012221716",
            sector="Healthcare",
            country="CH",
            currency="CHF",
        ),
    ]


@pytest.fixture
def in_memory_repo() -> InMemoryStockRepository:
    """Ein InMemoryStockRepository mit drei vorgeladenen Sample-Stocks."""
    repo = InMemoryStockRepository()
    for stock in _make_sample_stocks():
        repo.add(stock)
    return repo


@pytest_asyncio.fixture
async def http_client(
    in_memory_repo: InMemoryStockRepository,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient gegen die FastAPI-App mit InMemory-Repository als Override.

    Keine echte Datenbankverbindung — geeignet für Integrationstests der
    HTTP-Schicht ohne externe Abhängigkeiten.
    """
    app = create_app()

    # Dependency-Override: ersetzt SQLAlchemy-Adapter durch In-Memory-Variante
    app.dependency_overrides[get_stock_repository] = lambda: in_memory_repo

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
