# backend/domain/repositories/memo_batch_job_repository.py
"""Port fuer MemoBatchJob-Persistenz."""

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.memo_batch_job import MemoBatchJob


class MemoBatchJobRepository(ABC):
    """Abstrakte Schnittstelle fuer Job-State-Persistenz.

    UPSERT-Semantik: bei Konflikt werden id und created_at als
    Lifecycle-Marker NICHT ueberschrieben (analog research_memos).
    """

    @abstractmethod
    async def save(self, job: MemoBatchJob) -> None:
        """Persistiert oder aktualisiert einen Job."""

    @abstractmethod
    async def get(self, job_id: UUID) -> MemoBatchJob | None:
        """Laedt einen Job per ID, oder None wenn unknown."""

    @abstractmethod
    async def list_by_status(self, status: str) -> list[MemoBatchJob]:
        """Gibt alle Jobs mit dem angegebenen Status zurueck."""
