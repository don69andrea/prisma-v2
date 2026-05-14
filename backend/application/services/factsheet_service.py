"""FactsheetService — kombiniert Stock-Stammdaten mit neuestem Ranking-Snapshot."""

from typing import Any

from backend.domain.entities.stock import Stock
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.stock_repository import StockRepository


class StockNotFound(Exception):
    def __init__(self, ticker: str) -> None:
        super().__init__(f"Stock '{ticker.upper()}' not found")
        self.ticker = ticker


class FactsheetService:
    def __init__(
        self,
        stock_repo: StockRepository,
        run_repo: RankingRunRepository,
    ) -> None:
        self._stock_repo = stock_repo
        self._run_repo = run_repo

    async def get_factsheet(self, ticker: str) -> tuple[Stock, dict[str, Any] | None]:
        """Gibt Stock-Entity und neuesten Ranking-Snapshot zurück.

        Raises:
            StockNotFound: Wenn kein Stock mit diesem Ticker existiert.
        """
        stock = await self._stock_repo.get_by_ticker(ticker)
        if stock is None:
            raise StockNotFound(ticker)
        raw = await self._run_repo.get_latest_ticker_result(ticker)
        return stock, raw
