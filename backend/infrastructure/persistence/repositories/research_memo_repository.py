"""SQLAlchemy-Adapter für ResearchMemoRepository."""

from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo
from backend.domain.repositories.research_memo_repository import (
    ResearchMemoRepository,
)
from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM


class SQLAResearchMemoRepository(ResearchMemoRepository):
    """SQLAlchemy-Implementation des ResearchMemoRepository-Ports.

    Eigene session_factory pro Operation (Pattern aus SQLACostLogRepository,
    PR #25) — vermeidet Transaction-Leaks zwischen Request-Handler und
    Repository-Layer.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, memo: ResearchMemo) -> None:
        async with self._session_factory() as session:
            stmt = (
                pg_insert(ResearchMemoORM)
                .values(
                    id=memo.id,
                    stock_id=memo.stock_id,
                    model_run_id=memo.model_run_id,
                    language=memo.language,
                    created_at=memo.created_at,
                    one_liner=memo.one_liner,
                    ranking_interpretation=memo.ranking_interpretation,
                    sweet_spot=memo.sweet_spot,
                    sweet_spot_explanation=memo.sweet_spot_explanation,
                    contradictions=[c.model_dump() for c in memo.contradictions],
                    key_strengths=memo.key_strengths,
                    key_risks=memo.key_risks,
                    confidence=memo.confidence,
                    model_version=memo.model_version,
                    is_error=memo.is_error,
                )
                .on_conflict_do_update(
                    constraint="uq_research_memos_stock_run_lang",
                    set_={
                        "one_liner": memo.one_liner,
                        "ranking_interpretation": memo.ranking_interpretation,
                        "sweet_spot": memo.sweet_spot,
                        "sweet_spot_explanation": memo.sweet_spot_explanation,
                        "contradictions": [c.model_dump() for c in memo.contradictions],
                        "key_strengths": memo.key_strengths,
                        "key_risks": memo.key_risks,
                        "confidence": memo.confidence,
                        "model_version": memo.model_version,
                        "is_error": memo.is_error,
                        # created_at bewusst NICHT im Set — Lifecycle-Marker bleibt
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def get(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        language: Literal["de", "en"] = "de",
    ) -> ResearchMemo | None:
        async with self._session_factory() as session:
            stmt = select(ResearchMemoORM).where(
                ResearchMemoORM.stock_id == stock_id,
                ResearchMemoORM.model_run_id == model_run_id,
                ResearchMemoORM.language == language,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return _orm_to_entity(row) if row else None

    async def list_by_run(
        self,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
    ) -> list[ResearchMemo]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ResearchMemoORM)
                .where(ResearchMemoORM.model_run_id == model_run_id)
                .where(ResearchMemoORM.language == language)
                # F6: Sekundär-Sort nach id für Determinismus bei gleicher created_at.
                # Möglich bei Parallel-Batch-Inserts mit Semaphore(3): mehrere Memos
                # können denselben Timestamp bekommen → ohne id-Sort non-deterministisch.
                .order_by(ResearchMemoORM.created_at.asc(), ResearchMemoORM.id.asc())
            )
            rows = result.scalars().all()
            return [_orm_to_entity(row) for row in rows]


def _orm_to_entity(row: ResearchMemoORM) -> ResearchMemo:
    """Mapping ORM-Row → Domain-Entity. JSONB-Listen → Pydantic-Klassen."""
    return ResearchMemo(
        id=row.id,
        stock_id=row.stock_id,
        model_run_id=row.model_run_id,
        language=row.language,  # type: ignore[arg-type]
        created_at=row.created_at,
        one_liner=row.one_liner,
        ranking_interpretation=row.ranking_interpretation,
        sweet_spot=row.sweet_spot,
        sweet_spot_explanation=row.sweet_spot_explanation,
        contradictions=[ContradictionItem(**cast(dict[str, Any], d)) for d in row.contradictions],
        key_strengths=[str(s) for s in row.key_strengths],
        key_risks=[str(s) for s in row.key_risks],
        confidence=row.confidence,  # type: ignore[arg-type]
        model_version=row.model_version,
        is_error=row.is_error,
    )
