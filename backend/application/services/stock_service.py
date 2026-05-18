"""StockService — Use-Case-Orchestrierung für Stock-Abfragen."""

from backend.domain.entities.stock import Stock
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.stock_repository import StockRepository

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


class StockNotFound(Exception):
    def __init__(self, ticker: str) -> None:
        super().__init__(f"Stock '{ticker.upper()}' not found")
        self.ticker = ticker


class StockService:
    """Kapselt die Geschäftslogik rund um Stock-Abfragen."""

    def __init__(
        self,
        repository: StockRepository,
        market_data_provider: MarketDataProvider,
    ) -> None:
        self._repository = repository
        self._market_data_provider = market_data_provider

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        """Sucht eine Stock-Entity anhand des Ticker-Symbols (case-insensitive).

        Args:
            ticker: Ticker-Symbol (wird intern zu Uppercase normalisiert).

        Returns:
            Stock-Entity oder None wenn kein Treffer gefunden.
        """
        return await self._repository.get_by_ticker(ticker.upper())

    async def list_stocks(
        self,
        limit: int = _DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Stock]:
        """Gibt eine paginierte Stock-Liste zurück.

        Raises:
            ValueError: Wenn limit oder offset ausserhalb des erlaubten Bereichs.
        """
        if limit < 1 or limit > _MAX_LIMIT:
            raise ValueError(f"limit muss zwischen 1 und {_MAX_LIMIT} liegen, erhalten: {limit}")
        if offset < 0:
            raise ValueError(f"offset muss >= 0 sein, erhalten: {offset}")

        return await self._repository.list(limit=limit, offset=offset)

    async def get_price_series(
        self,
        ticker: str,
        days: int = 252,
    ) -> tuple[str, list[dict[str, str | float]]]:
        """Gibt Preiszeitreihe für einen Ticker zurück (letzte `days` Handelstage).

        Args:
            ticker: Ticker-Symbol (case-insensitive).
            days:   Anzahl Handelstage, 1–504. Default 252 (≈1 Jahr).

        Returns:
            Tuple (normalisierter_ticker, liste_von_{date, close}-dicts).

        Raises:
            StockNotFound: Wenn kein Stock mit diesem Ticker existiert.
        """
        ticker_upper = ticker.upper()
        stock = await self._repository.get_by_ticker(ticker_upper)
        if stock is None:
            raise StockNotFound(ticker_upper)

        df = await self._market_data_provider.get_prices([ticker_upper])
        series = df[ticker_upper].tail(days)
        prices = [
            {"date": idx.date().isoformat(), "close": round(float(val), 4)}
            for idx, val in series.items()
        ]
        return ticker_upper, prices
