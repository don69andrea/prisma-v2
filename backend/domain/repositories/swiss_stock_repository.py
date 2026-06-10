# backend/domain/repositories/swiss_stock_repository.py
"""Abstraktes Repository-Interface für SwissStock-Entitäten (Port, nicht Adapter)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from backend.domain.entities.swiss_stock import SwissStock


class SwissStockRepository(ABC):
    """Vertrag zwischen Application-Layer und Persistence-Adapter für Swiss Stocks."""

    @abstractmethod
    async def get_by_ticker(self, ticker: str) -> SwissStock | None:
        """Sucht einen Swiss Stock anhand des Ticker-Symbols (case-insensitive).

        Gibt None zurück wenn kein Treffer — kein Exception-Missbrauch.
        """
        ...

    @abstractmethod
    async def list_by_exchange(
        self,
        exchange: Literal["XSWX"] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SwissStock]:
        """Gibt paginierte Swiss Stocks zurück, optional gefiltert nach Exchange.

        exchange=None → alle Swiss Stocks (WHERE exchange IS NOT NULL).
        exchange="XSWX" → nur XSWX-notierte Titel.
        """
        ...

    @abstractmethod
    async def upsert_batch(self, stocks: list[SwissStock]) -> int:
        """Idempotentes Einfügen/Aktualisieren einer Liste von Swiss Stocks.

        Nutzt ON CONFLICT (ticker) DO UPDATE.
        Gibt Anzahl betroffener Rows zurück.
        """
        ...
