"""FactsheetService — kombiniert Stock-Stammdaten mit neuestem Ranking-Snapshot."""

from typing import Any

from backend.application.services.stock_service import StockNotFound, _normalize_ticker
from backend.domain.entities.stock import Stock
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.stock_repository import StockRepository


class FactsheetService:
    """Kombiniert Stock-Stammdaten mit dem neuesten Ranking-Snapshot eines Tickers."""

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
        normalized = _normalize_ticker(ticker)
        stock = await self._stock_repo.get_by_ticker(normalized)
        if stock is None:
            raise StockNotFound(ticker)
        raw = await self._run_repo.get_latest_ticker_result(normalized)
        return stock, raw
