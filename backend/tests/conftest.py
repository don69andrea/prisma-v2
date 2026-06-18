"""Gemeinsame pytest-Fixtures für alle Test-Ebenen."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from uuid import UUID

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

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        for stock in self._stocks:
            if stock.ticker == ticker.upper():
                return stock
        return None

    async def get(self, stock_id: UUID) -> Stock | None:
        for stock in self._stocks:
            if stock.id == stock_id:
                return stock
        return None

    async def list_by_ids(self, stock_ids: list[UUID]) -> list[Stock]:
        wanted: set[UUID] = set(stock_ids)
        return [s for s in self._stocks if s.id in wanted]

    async def list_by_tickers(self, tickers: list[str]) -> list[Stock]:
        wanted: set[str] = {t.upper() for t in tickers}
        return [s for s in self._stocks if s.ticker in wanted]

    # `list` am Ende — siehe Hinweis im Port.
    async def list(self, limit: int, offset: int) -> list[Stock]:
        sorted_stocks = sorted(self._stocks, key=lambda s: s.ticker)
        return sorted_stocks[offset : offset + limit]


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
def sample_stocks() -> list[Stock]:
    """Drei beispielhaft befüllte Stock-Entities (AAPL, NESN, NOVN).

    Public Fixture-Wrapper um den privaten `_make_sample_stocks`-Builder —
    Tests nutzen diese Fixture statt die private Funktion direkt zu importieren.
    """
    return _make_sample_stocks()


@pytest.fixture
def in_memory_repo(sample_stocks: list[Stock]) -> InMemoryStockRepository:
    """Ein InMemoryStockRepository mit drei vorgeladenen Sample-Stocks."""
    repo = InMemoryStockRepository()
    for stock in sample_stocks:
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
    from uuid import uuid4 as _uuid4

    from backend.domain.entities.user import User as _User
    from backend.domain.entities.user import UserRole as _UserRole
    from backend.interfaces.rest.dependencies import require_admin_role, require_current_user

    _fake = _User(
        id=_uuid4(),
        email="test-admin@example.com",
        hashed_password="x",
        role=_UserRole.admin,
        is_active=True,
    )

    app = create_app()

    app.dependency_overrides[get_stock_repository] = lambda: in_memory_repo
    app.dependency_overrides[require_current_user] = lambda: _fake
    app.dependency_overrides[require_admin_role] = lambda: _fake

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
