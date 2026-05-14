"""Integrationstests für GET /api/v1/stocks/{ticker}/factsheet."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.application.services.factsheet_service import FactsheetService
from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.stock import Stock
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_factsheet_service

pytestmark = pytest.mark.integration

_AAPL_ID = uuid.uuid4()
_AAPL = Stock(
    id=_AAPL_ID,
    ticker="AAPL",
    name="Apple Inc.",
    isin="US0378331005",
    sector="Technology",
    country="US",
    currency="USD",
)
_AAPL_RANKING: dict[str, Any] = {
    "ticker": "AAPL",
    "total_rank": 1,
    "weighted_avg": 0.85,
    "is_sweet_spot": True,
    "per_model_ranks": {
        "quality_classic": 1,
        "diversification": 2,
        "trend_momentum": 1,
        "value_alpha_potential": 3,
        "alpha": 2,
    },
}


class _FakeStockRepo(StockRepository):
    def __init__(self, stocks: list[Stock]) -> None:
        self._by_ticker = {s.ticker: s for s in stocks}
        self._by_id = {s.id: s for s in stocks}

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        return self._by_ticker.get(ticker.upper())

    async def get(self, stock_id: UUID) -> Stock | None:
        return self._by_id.get(stock_id)

    async def list_by_ids(self, stock_ids: list[UUID]) -> list[Stock]:
        return [self._by_id[i] for i in stock_ids if i in self._by_id]

    async def list_by_tickers(self, tickers: list[str]) -> list[Stock]:
        return [self._by_ticker[t.upper()] for t in tickers if t.upper() in self._by_ticker]

    async def list(self, limit: int, offset: int) -> list[Stock]:
        return sorted(self._by_ticker.values(), key=lambda s: s.ticker)[offset : offset + limit]


class _FakeRunRepo(RankingRunRepository):
    def __init__(self, results: dict[str, dict[str, Any]] | None = None) -> None:
        self._results = {k.upper(): v for k, v in (results or {}).items()}

    async def get(self, run_id: UUID) -> RankingRun | None:
        raise NotImplementedError

    async def save(self, run: RankingRun) -> None:
        raise NotImplementedError

    async def list_by_universe(self, universe_id: UUID) -> list[RankingRun]:
        raise NotImplementedError

    async def save_results(self, run_id: UUID, results: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    async def get_results(self, run_id: UUID) -> list[dict[str, Any]] | None:
        raise NotImplementedError

    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        return self._results.get(ticker.upper())


def _make_app(
    stocks: list[Stock],
    run_results: dict[str, dict[str, Any]] | None = None,
) -> Any:
    app = create_app()
    stock_repo = _FakeStockRepo(stocks)
    run_repo = _FakeRunRepo(run_results)
    app.dependency_overrides[get_factsheet_service] = lambda: FactsheetService(
        stock_repo=stock_repo, run_repo=run_repo
    )
    return app


@pytest_asyncio.fixture
async def client_with_ranking() -> AsyncGenerator[AsyncClient, None]:
    """Client: AAPL vorhanden + Ranking-Snapshot verfügbar."""
    app = _make_app([_AAPL], {"AAPL": _AAPL_RANKING})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def client_no_ranking() -> AsyncGenerator[AsyncClient, None]:
    """Client: AAPL vorhanden, aber keine abgeschlossenen Runs."""
    app = _make_app([_AAPL], {})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def test_factsheet_known_ticker_returns_200(client_with_ranking: AsyncClient) -> None:
    response = await client_with_ranking.get("/api/v1/stocks/AAPL/factsheet")
    assert response.status_code == 200


async def test_factsheet_unknown_ticker_returns_404(client_with_ranking: AsyncClient) -> None:
    response = await client_with_ranking.get("/api/v1/stocks/UNKNOWN/factsheet")
    assert response.status_code == 404


async def test_factsheet_response_contains_stock_and_ranking(
    client_with_ranking: AsyncClient,
) -> None:
    body = (await client_with_ranking.get("/api/v1/stocks/AAPL/factsheet")).json()
    assert body["stock"]["ticker"] == "AAPL"
    assert body["latest_ranking"] is not None
    assert body["latest_ranking"]["total_rank"] == 1
    assert body["latest_ranking"]["is_sweet_spot"] is True
    assert "per_model_ranks" in body["latest_ranking"]


async def test_factsheet_null_snapshot_when_no_ranking(client_no_ranking: AsyncClient) -> None:
    body = (await client_no_ranking.get("/api/v1/stocks/AAPL/factsheet")).json()
    assert body["stock"]["ticker"] == "AAPL"
    assert body["latest_ranking"] is None


async def test_factsheet_ticker_case_insensitive(client_with_ranking: AsyncClient) -> None:
    response = await client_with_ranking.get("/api/v1/stocks/aapl/factsheet")
    assert response.status_code == 200
    assert response.json()["stock"]["ticker"] == "AAPL"
