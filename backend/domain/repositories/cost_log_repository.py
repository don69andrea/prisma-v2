"""Abstraktes Repository-Interface für LLM-Cost-Audit-Log (Port, nicht Adapter).

Das Application-Layer (CostTracker) kennt nur diesen Port — keine
SQLAlchemy- oder ORM-Imports. Damit bleibt AGENTS.md §2
("Application kennt keine Frameworks") gewahrt.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §5 + §9.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from backend.domain.cost_summary import CostBreakdown


@dataclass(frozen=True)
class CostLogEntry:
    """Eingabe für `record()` — ein einzelner Audit-Eintrag.

    Bewusst ohne `created_at`: der Persistence-Adapter setzt den Zeitstempel
    konsistent über alle Einträge (Server-Zeit, UTC).
    """

    provider: str
    model: str
    feature: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    request_id: str | None = None


class CostLogRepository(ABC):
    """Definiert den Vertrag zwischen Application-Layer und Persistence-Adapter.

    Konkrete Implementierungen leben im Infrastructure-Layer.
    """

    @abstractmethod
    async def record(self, entry: CostLogEntry) -> None:
        """Persistiert einen Audit-Eintrag in einer eigenen Transaktion.

        Wichtig: die Implementierung muss ihre eigene Session/Transaktion
        verwenden, damit Audit-Inserts nicht versehentlich laufende
        Business-Operationen mit-committen.
        """
        ...

    @abstractmethod
    async def current_month_total_usd(self) -> Decimal:
        """Liefert SUM(cost_usd) für den aktuellen Kalender-Monat (UTC).

        Synchron mit Anthropic-Console-Spend-Limit (Kalender-Monat UTC).
        """
        ...

    @abstractmethod
    async def current_month_breakdown(self, last_n: int) -> CostBreakdown:
        """Aggregat: by_model, by_feature, letzte N Calls — für Admin-Endpoint."""
        ...

    @abstractmethod
    async def check_cap_atomic(
        self, estimated_usd: Decimal, cap_usd: Decimal, threshold: Decimal
    ) -> bool:
        """Atomarer Cap-Check via PostgreSQL Advisory Lock — multi-process-sicher.

        Gibt True zurück wenn (current_month_total + estimated_usd) <= cap_usd * threshold.
        Verwendet pg_try_advisory_xact_lock um Race Conditions zwischen Prozessen zu verhindern.
        Muss innerhalb einer Transaktion aufgerufen werden.
        """
        ...
