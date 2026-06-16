"""Abstraktes Repository-Interface für Universe-Entitäten."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.universe import Universe


class DuplicateUniverseNameError(ValueError):
    """Wird geworfen wenn ein Universe mit gleichem Namen bereits existiert.

    `universes.name` hat einen UNIQUE-Index (`ix_universes_name`). Da
    `save()` per `ON CONFLICT (id) DO UPDATE` arbeitet und `create_universe()`
    immer eine neue UUID generiert, greift der Conflict-Handler nie für
    Namens-Duplikate — die rohe `IntegrityError` muss daher beim Speichern
    abgefangen und hierher übersetzt werden (Audit-Finding K-4/F-BTCR-3).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Universe mit name={name!r} existiert bereits")


class UniverseRepository(ABC):
    @abstractmethod
    async def get(self, universe_id: UUID) -> Universe | None: ...

    @abstractmethod
    async def list(self) -> list[Universe]: ...

    @abstractmethod
    async def save(self, universe: Universe) -> None:
        """Persistiert ein Universe (Insert oder Update per ID).

        Wirft `DuplicateUniverseNameError` wenn `universe.name` bereits von
        einem anderen Universe belegt ist.
        """
