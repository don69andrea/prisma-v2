"""SQLAlchemy implementation of UserRepository."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.user import User, UserRole
from backend.domain.repositories.user_repository import UserRepository
from backend.infrastructure.persistence.models.user import UserORM


class SQLAUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return self._to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        # Case-insensitiver Lookup: E-Mails werden als case-insensitive behandelt.
        # Verhindert "Login schlägt fehl egal was man eingibt", wenn der Admin z.B.
        # mit "Admin@Prisma.ch" geseedet wurde, der Nutzer aber "admin@prisma.ch" tippt.
        normalized = email.strip().lower()
        stmt = select(UserORM).where(func.lower(UserORM.email) == normalized)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def list_all(self) -> list[User]:
        stmt = select(UserORM).order_by(UserORM.created_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, user: User) -> None:
        stmt = (
            pg_insert(UserORM)
            .values(
                id=user.id,
                email=user.email,
                hashed_password=user.hashed_password,
                first_name=user.first_name,
                last_name=user.last_name,
                role=user.role.value,
                is_active=user.is_active,
                created_at=user.created_at,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "email": user.email,
                    "hashed_password": user.hashed_password,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role.value,
                    "is_active": user.is_active,
                },
            )
        )
        await self._session.execute(stmt)

    async def delete_user_data(self, user_id: UUID) -> None:
        """Removes all personal data rows for the user. Does not delete the user record."""
        from backend.infrastructure.persistence.models.alert import AlertORM
        from backend.infrastructure.persistence.models.backtest_result import BacktestResultORM
        from backend.infrastructure.persistence.models.decision_audit_log import DecisionAuditLogORM
        from backend.infrastructure.persistence.models.investor_profile import InvestorProfileORM
        from backend.infrastructure.persistence.models.llm_call_log import LLMCallLogORM
        from backend.infrastructure.persistence.models.memo_batch_job import MemoBatchJobORM
        from backend.infrastructure.persistence.models.ranking_run import RankingRunORM
        from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM

        # user_id column added in migration 0027
        for orm_cls in (
            AlertORM,
            BacktestResultORM,
            DecisionAuditLogORM,
            InvestorProfileORM,
            LLMCallLogORM,
            MemoBatchJobORM,
            RankingRunORM,
            ResearchMemoORM,
        ):
            await self._session.execute(delete(orm_cls).where(orm_cls.user_id == user_id))

    def _to_domain(self, row: UserORM) -> User:
        return User(
            id=row.id,
            email=row.email,
            hashed_password=row.hashed_password,
            first_name=row.first_name,
            last_name=row.last_name,
            role=UserRole(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
        )
