"""Application-Service für den Schweizer Aktienmarkt."""

from __future__ import annotations

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.domain.services.swiss_quant_scorer import SwissQuantScorer
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore


class SwissMarketService:
    def __init__(
        self,
        repo: SwissStockRepository,
        market_data: SwissMarketDataProvider | None = None,
    ) -> None:
        self._repo = repo
        self._market_data = market_data
        self._scorer = SwissQuantScorer()

    async def list_smi_stocks(self) -> list[SwissStock]:
        """Gibt alle XSWX-kotierten Swiss Stocks zurück (SMI-Universum)."""
        return await self._repo.list_by_exchange(exchange="XSWX")

    async def get_swiss_stock(self, ticker: str) -> SwissStock | None:
        """Sucht einen Swiss Stock anhand des Tickers (case-insensitive)."""
        return await self._repo.get_by_ticker(ticker.upper())

    async def refresh_market_data(self, ticker: str) -> SwissStock:
        """Aktualisiert market_cap_chf für einen Swiss Stock aus yfinance und persistiert."""
        if self._market_data is None:
            raise RuntimeError(
                "SwissMarketService ohne MarketDataProvider konfiguriert — "
                "verwende get_swiss_market_service() aus dependencies.py"
            )
        upper = ticker.upper()
        existing = await self._repo.get_by_ticker(upper)
        if existing is None:
            raise ValueError(f"Swiss Stock '{upper}' nicht gefunden")
        fundamentals = await self._market_data.get_fundamentals(upper)
        updated = SwissStock(
            id=existing.id,
            ticker=existing.ticker,
            isin=existing.isin,
            name=existing.name,
            exchange=existing.exchange,
            sector=existing.sector,
            market_cap_chf=fundamentals.market_cap_chf,
        )
        await self._repo.upsert_batch([updated])
        return updated

    async def score_stock(self, ticker: str) -> SwissQuantScore:
        """Berechnet den Swiss Quant Score für einen Ticker."""
        if self._market_data is None:
            raise RuntimeError("SwissMarketService ohne MarketDataProvider konfiguriert")
        upper = ticker.upper()
        existing = await self._repo.get_by_ticker(upper)
        if existing is None:
            raise ValueError(f"Swiss Stock '{upper}' nicht gefunden")
        fundamentals = await self._market_data.get_fundamentals(upper)
        return self._scorer.score(upper, fundamentals)
