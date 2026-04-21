"""StockService — Use-Case-Orchestrierung für Stock-Abfragen."""

from backend.domain.entities.stock import Stock
from backend.domain.repositories.stock_repository import StockRepository

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


class StockService:
    """Kapselt die Geschäftslogik rund um Stock-Abfragen.

    Kennt nur den abstrakten StockRepository-Port, nie eine konkrete
    Datenbankimplementierung (Dependency-Inversion-Principle).
    """

    def __init__(self, repository: StockRepository) -> None:
        self._repository = repository

    async def list_stocks(
        self,
        limit: int = _DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Stock]:
        """Gibt eine paginierte Stock-Liste zurück.

        Args:
            limit:  Maximale Anzahl Ergebnisse. Muss zwischen 1 und 200 liegen.
            offset: Anzahl zu überspringender Einträge (0-basiert).

        Raises:
            ValueError: Wenn limit oder offset ausserhalb des erlaubten Bereichs.
        """
        if limit < 1 or limit > _MAX_LIMIT:
            raise ValueError(f"limit muss zwischen 1 und {_MAX_LIMIT} liegen, erhalten: {limit}")
        if offset < 0:
            raise ValueError(f"offset muss >= 0 sein, erhalten: {offset}")

        return await self._repository.list(limit=limit, offset=offset)
