"""Repository-Port für Alerts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.alert import Alert


class AlertRepository(ABC):
    @abstractmethod
    async def save(self, alert: Alert) -> None: ...

    @abstractmethod
    async def get_by_id(self, alert_id: UUID) -> Alert | None: ...

    @abstractmethod
    async def list_active(self) -> list[Alert]: ...

    @abstractmethod
    async def list_by_owner(self, target: str) -> list[Alert]: ...

    @abstractmethod
    async def delete(self, alert_id: UUID) -> None: ...

    @abstractmethod
    async def update(self, alert: Alert) -> None: ...
