"""Integration-Tests für SQLAResearchMemoRepository gegen Live-Postgres."""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo
from backend.infrastructure.persistence.repositories.research_memo_repository import (
    SQLAResearchMemoRepository,
)

pytestmark = [pytest.mark.integration]


def _new_memo(
    stock_id: uuid.UUID,
    model_run_id: uuid.UUID,
    *,
    language: str = "de",
    one_liner: str = "Initialer Memo-Text",
) -> ResearchMemo:
    return ResearchMemo(
        id=uuid.uuid4(),
        stock_id=stock_id,
        model_run_id=model_run_id,
        language=language,  # type: ignore[arg-type]
        created_at=datetime.now(UTC),
        one_liner=one_liner,
        ranking_interpretation="x" * 200,
        sweet_spot=False,
        sweet_spot_explanation=None,
        contradictions=[
            ContradictionItem(model_a="Quality", model_b="Trend", description="x" * 50)
        ],
        key_strengths=["Stabilität"],
        key_risks=["FX"],
        confidence="medium",
        model_version="claude-sonnet-4-6@20260101",
    )


@pytest_asyncio.fixture
async def seed_stock_and_run(db_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Erzeugt Stock + Universe + RankingRun, returned (stock_id, run_id)."""
    stock_id = uuid.uuid4()
    run_id = uuid.uuid4()
    universe_id = uuid.uuid4()

    await db_session.execute(
        text(
            "INSERT INTO stocks (id, ticker, name, currency) VALUES (:id, 'NESN', 'Nestle', 'CHF')"
        ),
        {"id": stock_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, region, tickers) "
            "VALUES (:id, 'TEST', 'CH', ARRAY['NESN']::varchar[])"
        ),
        {"id": universe_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO ranking_runs (id, universe_id, status, weight_config, created_at) "
            "VALUES (:id, :uid, 'completed', '{}', now())"
        ),
        {"id": run_id, "uid": universe_id},
    )
    await db_session.commit()
    return stock_id, run_id


class TestRoundtripAndUpsert:
    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_save_then_get_returns_same_memo(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(session_factory)
        memo = _new_memo(stock_id, run_id)

        await repo.save(memo)
        got = await repo.get(stock_id, run_id)

        assert got is not None
        assert got.id == memo.id
        assert got.one_liner == memo.one_liner
        assert len(got.contradictions) == 1
        assert got.contradictions[0].model_a == "Quality"

    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_get_nonexistent_returns_none(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(session_factory)
        got = await repo.get(stock_id, run_id)
        assert got is None

    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_upsert_overwrites_fields_keeps_created_at(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(session_factory)

        memo_v1 = _new_memo(stock_id, run_id, one_liner="erste Version")
        await repo.save(memo_v1)
        got_v1 = await repo.get(stock_id, run_id)
        assert got_v1 is not None
        original_created_at = got_v1.created_at

        memo_v2 = _new_memo(stock_id, run_id, one_liner="zweite Version")
        await repo.save(memo_v2)
        got_v2 = await repo.get(stock_id, run_id)

        assert got_v2 is not None
        assert got_v2.one_liner == "zweite Version"  # überschrieben
        assert got_v2.created_at == original_created_at  # NICHT überschrieben

    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_multi_language_coexists(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(session_factory)

        memo_de = _new_memo(stock_id, run_id, language="de", one_liner="Deutsch-Memo")
        memo_en = _new_memo(stock_id, run_id, language="en", one_liner="English memo")

        await repo.save(memo_de)
        await repo.save(memo_en)

        got_de = await repo.get(stock_id, run_id, language="de")
        got_en = await repo.get(stock_id, run_id, language="en")

        assert got_de is not None and got_de.one_liner == "Deutsch-Memo"
        assert got_en is not None and got_en.one_liner == "English memo"


class TestCascade:
    @pytest.mark.usefixtures("truncate_research_memos")
    async def test_delete_stock_cascades_to_memo(
        self,
        seed_stock_and_run: tuple[uuid.UUID, uuid.UUID],
        db_session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        stock_id, run_id = seed_stock_and_run
        repo = SQLAResearchMemoRepository(session_factory)

        memo = _new_memo(stock_id, run_id)
        await repo.save(memo)

        await db_session.execute(text("DELETE FROM stocks WHERE id = :id"), {"id": stock_id})
        await db_session.commit()

        got = await repo.get(stock_id, run_id)
        assert got is None
