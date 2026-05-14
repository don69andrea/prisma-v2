"""Port für ResearchMemo-Persistenz."""

from abc import ABC, abstractmethod
from typing import Literal
from uuid import UUID

from backend.domain.entities.research_memo import ResearchMemo


class ResearchMemoRepository(ABC):
    """Port für ResearchMemo-Persistenz.

    Konkrete Implementierungen in backend/infrastructure/persistence/repositories/.
    """

    @abstractmethod
    async def save(self, memo: ResearchMemo) -> None:
        """Persistiere ODER überschreibe (UPSERT) ein Memo.

        Konflikt-Strategie: bei UNIQUE-Verletzung auf
        (stock_id, model_run_id, language) wird der existierende Eintrag
        überschrieben — alle Schema-Felder, aber NICHT created_at.
        """
        ...

    @abstractmethod
    async def get(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        language: Literal["de", "en"] = "de",
    ) -> ResearchMemo | None:
        """Lade existierendes Memo oder None."""
        ...

    @abstractmethod
    async def list_by_run(
        self,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
    ) -> list[ResearchMemo]:
        """Liefert alle Memos fuer einen Run + Sprache, leere Liste wenn keine."""
        ...
