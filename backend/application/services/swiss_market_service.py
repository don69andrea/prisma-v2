"""Application-Service für den Schweizer Aktienmarkt."""

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository


class SwissMarketService:
    def __init__(self, repo: SwissStockRepository) -> None:
        self._repo = repo

    async def list_smi_stocks(self) -> list[SwissStock]:
        """Gibt alle XSWX-kotierten Swiss Stocks zurück (SMI-Universum)."""
        return await self._repo.list_by_exchange(exchange="XSWX")

    async def get_swiss_stock(self, ticker: str) -> SwissStock | None:
        """Sucht einen Swiss Stock anhand des Tickers (case-insensitive)."""
        return await self._repo.get_by_ticker(ticker.upper())
