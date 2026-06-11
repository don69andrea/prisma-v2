"""SQLAlchemy-Implementierung des InvestorProfileRepository-Ports."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.investor_profile import InvestorProfile
from backend.domain.repositories.investor_profile_repository import InvestorProfileRepository
from backend.infrastructure.persistence.models.investor_profile import InvestorProfileORM


class SQLAInvestorProfileRepository(InvestorProfileRepository):
    """Liest und schreibt InvestorProfile-Entitäten via AsyncSession in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, profile: InvestorProfile) -> None:
        orm = self._to_orm(profile)
        await self._session.merge(orm)

    async def get_by_session_id(self, session_id: str) -> InvestorProfile | None:
        stmt = select(InvestorProfileORM).where(InvestorProfileORM.session_id == session_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_orm(p: InvestorProfile) -> InvestorProfileORM:
        return InvestorProfileORM(
            id=p.id,
            session_id=p.session_id,
            profession=p.profession,
            financial_knowledge=p.financial_knowledge,
            investment_goal=p.investment_goal,
            time_horizon=p.time_horizon,
            risk_profile=p.risk_profile,
            sector_affinity=list(p.sector_affinity),
            known_tickers=list(p.known_tickers),
            confidence_score=p.confidence_score,
            onboarding_complete=p.onboarding_complete,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    @staticmethod
    def _to_domain(r: InvestorProfileORM) -> InvestorProfile:
        def _utc(dt: datetime | None) -> datetime:
            if dt is None:
                return datetime.now(UTC)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

        return InvestorProfile(
            id=r.id,
            session_id=r.session_id,
            profession=r.profession,
            financial_knowledge=r.financial_knowledge,  # type: ignore[arg-type]
            investment_goal=r.investment_goal,  # type: ignore[arg-type]
            time_horizon=r.time_horizon,  # type: ignore[arg-type]
            risk_profile=r.risk_profile,  # type: ignore[arg-type]
            sector_affinity=list(r.sector_affinity or []),
            known_tickers=list(r.known_tickers or []),
            confidence_score=r.confidence_score,
            onboarding_complete=r.onboarding_complete,
            created_at=_utc(r.created_at),
            updated_at=_utc(r.updated_at),
        )
