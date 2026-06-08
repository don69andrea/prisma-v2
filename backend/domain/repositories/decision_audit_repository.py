"""Domain Repository Interface: DecisionAuditRepository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.decision_audit_record import DecisionAuditRecord


class DecisionAuditRepository(ABC):
    @abstractmethod
    async def save(self, record: DecisionAuditRecord) -> None: ...

    @abstractmethod
    async def list_by_ticker(
        self, ticker: str, limit: int = 10
    ) -> list[DecisionAuditRecord]: ...
