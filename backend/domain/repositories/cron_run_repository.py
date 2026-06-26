from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.models.cron_run_record import CronRunRecord


class CronRunRepository(ABC):
    @abstractmethod
    async def start_run(self, job_name: str) -> str:
        """Legt neuen Run an, gibt run_id zurück."""

    @abstractmethod
    async def finish_run(
        self,
        run_id: str,
        status: str,
        records_saved: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        """Schliesst einen Run ab."""

    @abstractmethod
    async def get_latest_per_job(self) -> list[CronRunRecord]:
        """Gibt den neuesten Run pro Job zurück."""
