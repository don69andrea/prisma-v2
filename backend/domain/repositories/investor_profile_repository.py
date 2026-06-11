"""Abstraktes Repository-Interface für InvestorProfile-Entitäten (Port)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.investor_profile import InvestorProfile


class InvestorProfileRepository(ABC):
    """Vertrag zwischen Application-Layer und Persistence-Adapter für InvestorProfiles."""

    @abstractmethod
    async def save(self, profile: InvestorProfile) -> None:
        """Persistiert ein InvestorProfile (INSERT oder UPDATE via session_id)."""
        ...

    @abstractmethod
    async def get_by_session_id(self, session_id: str) -> InvestorProfile | None:
        """Sucht ein Profil anhand der Session-ID. Gibt None zurück bei keinem Treffer."""
        ...
