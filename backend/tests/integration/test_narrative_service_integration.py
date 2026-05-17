"""Integration: NarrativeService gegen echte Postgres + StubAnthropicClient."""

import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.services.cost_tracker import CostTracker
from backend.application.services.narrative_service import NarrativeService
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.pricing import PRICING
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
from backend.infrastructure.persistence.repositories.cost_log_repository import (
    SQLACostLogRepository,
)
from backend.infrastructure.persistence.repositories.memo_batch_job_repository import (
    SQLAMemoBatchJobRepository,
)
from backend.infrastructure.persistence.repositories.ranking_run_repository import (
    SQLARankingRunRepository,
)
from backend.infrastructure.persistence.repositories.research_memo_repository import (
    SQLAResearchMemoRepository,
)
from backend.infrastructure.persistence.repositories.stock_repository import (
    SQLAStockRepository,
)
from backend.tests.fixtures.llm.stub_anthropic_client import StubAnthropicClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / "narrative"

# 3-Stock-Mini-Universe, aus Task 5 Sample-Results — ABBN nur im JSON,
# kein Stock-DB-Eintrag noetig da _extract_ranking_for_ticker nach ticker filtert.
_SAMPLE_RESULTS = [
    {
        "ticker": "NESN",
        "total_rank": 1,
        "weighted_avg": 8.4,
        "is_sweet_spot": True,
        "per_model_ranks": {
            "quality_classic": 8,
            "alpha": 12,
            "trend_momentum": 25,
            "value_alpha_potential": 60,
            "diversification": 5,
        },
    },
    {
        "ticker": "ROG",
        "total_rank": 2,
        "weighted_avg": 12.0,
        "is_sweet_spot": False,
        "per_model_ranks": {
            "quality_classic": 15,
            "alpha": 20,
            "trend_momentum": 18,
            "value_alpha_potential": 22,
            "diversification": 10,
        },
    },
    {
        "ticker": "ABBN",
        "total_rank": 3,
        "weighted_avg": 25.0,
        "is_sweet_spot": False,
        "per_model_ranks": {
            "quality_classic": 30,
            "alpha": 28,
            "trend_momentum": 35,
            "value_alpha_potential": 18,
            "diversification": 14,
        },
    },
]


@pytest_asyncio.fixture
async def seeded_run_with_stock(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[async_sessionmaker[AsyncSession], dict[str, UUID]], None]:
    """Persistiere 2 Stocks + Universe + RankingRun + Results.

    Gibt (session_factory, ids) zurueck — session_factory weil die SQLA-
    Repositories (ResearchMemo, CostLog) eine session_factory erwarten,
    keine Einzelsession.

    ids enthaelt:
      stock_id       — NESN (Haupt-Test-Stock)
      second_stock_id — ROG (fuer Cache-Hit-Smoke-Test)
      run_id         — RankingRun-UUID
    """
    stock_id = uuid4()
    second_stock_id = uuid4()
    run_id = uuid4()
    universe_id = uuid4()

    truncate_sql = text(
        "TRUNCATE research_memos, llm_call_log, ranking_runs, universes, stocks CASCADE"
    )

    async with session_factory() as session:
        # Vorherige Daten bereinigen
        await session.execute(truncate_sql)
        await session.commit()

        # Stocks einfuegen
        await session.execute(
            text(
                "INSERT INTO stocks (id, ticker, name, currency) "
                "VALUES (:id, 'NESN', 'Nestle', 'CHF')"
            ),
            {"id": stock_id},
        )
        await session.execute(
            text(
                "INSERT INTO stocks (id, ticker, name, currency) "
                "VALUES (:id, 'ROG', 'Roche', 'CHF')"
            ),
            {"id": second_stock_id},
        )

        # Universe mit beiden Tickers
        await session.execute(
            text(
                "INSERT INTO universes (id, name, region, tickers) "
                "VALUES (:id, 'TEST', 'CH', ARRAY['NESN', 'ROG', 'ABBN']::varchar[])"
            ),
            {"id": universe_id},
        )

        # RankingRun mit Results-JSON (3 Eintraege, 2 haben DB-Stock, 1 nur im JSON)
        # cast() als SQLAlchemy-Konstrukt statt ::jsonb (asyncpg versteht kein :param::cast)
        results_json = json.dumps(_SAMPLE_RESULTS)
        await session.execute(
            text(
                "INSERT INTO ranking_runs (id, universe_id, status, weight_config, results, created_at) "
                "VALUES (:id, :uid, 'completed', '{}', cast(:results as jsonb), now())"
            ),
            {
                "id": run_id,
                "uid": universe_id,
                "results": results_json,
            },
        )
        await session.commit()

    ids = {
        "stock_id": stock_id,
        "second_stock_id": second_stock_id,
        "run_id": run_id,
    }

    yield session_factory, ids

    # Cleanup nach dem Test
    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()


async def test_full_pipeline_top_quality_fixture(
    seeded_run_with_stock: tuple[async_sessionmaker[AsyncSession], dict[str, UUID]],
) -> None:
    """End-to-End: Stock + Run → Service ruft Stub-Anthropic → Memo in DB."""
    session_factory, ids = seeded_run_with_stock

    stub = StubAnthropicClient([FIXTURES / "top_quality_stock.json"])
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session_factory),
        pricing=PRICING,
        cap_usd=Decimal("20"),
    )
    async with session_factory() as session:
        service = NarrativeService(
            memo_repository=SQLAResearchMemoRepository(session_factory),
            run_repository=SQLARankingRunRepository(session),
            stock_repository=SQLAStockRepository(session),
            batch_repository=SQLAMemoBatchJobRepository(session_factory),
            llm_client=LLMClient(
                anthropic=stub,
                voyage=None,
                cost_tracker=cost_tracker,
                pricing=PRICING,
            ),
            prompt_loader=PromptTemplateLoader(),
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            stock_repo_factory=lambda s: SQLAStockRepository(session=s),
            run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
        )

        memo = await service.generate_memo(ids["stock_id"], ids["run_id"])

    assert memo.confidence == "high"
    assert memo.sweet_spot is True
    assert memo.model_version == "claude-sonnet-4-6"


async def test_full_pipeline_en(
    seeded_run_with_stock: tuple[async_sessionmaker[AsyncSession], dict[str, UUID]],
) -> None:
    """EN-Slice End-to-End: language='en' Memo persisted, abrufbar; DE-Pfad bleibt leer.

    Verifiziert die bilinguale Cache-Trennung: ein EN-Memo darf nicht beim
    DE-Lookup zurueckkommen (separate cache keys per language).
    """
    session_factory, ids = seeded_run_with_stock

    stub = StubAnthropicClient([FIXTURES / "top_quality_stock_en.json"])
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session_factory),
        pricing=PRICING,
        cap_usd=Decimal("20"),
    )
    async with session_factory() as session:
        service = NarrativeService(
            memo_repository=SQLAResearchMemoRepository(session_factory),
            run_repository=SQLARankingRunRepository(session),
            stock_repository=SQLAStockRepository(session),
            batch_repository=SQLAMemoBatchJobRepository(session_factory),
            llm_client=LLMClient(
                anthropic=stub,
                voyage=None,
                cost_tracker=cost_tracker,
                pricing=PRICING,
            ),
            prompt_loader=PromptTemplateLoader(),
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            stock_repo_factory=lambda s: SQLAStockRepository(session=s),
            run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
        )

        memo = await service.generate_memo(ids["stock_id"], ids["run_id"], language="en")

        assert memo.language == "en"
        assert memo.confidence == "high"
        assert memo.one_liner == ("Defensive quality core with low risk, weak reversion potential.")
        assert memo.model_version == "claude-sonnet-4-6"

        # Cache-Hit: EN-Memo wird beim get_memo(language="en") zurueckgegeben
        en_lookup = await service.get_memo(ids["stock_id"], ids["run_id"], language="en")
        assert en_lookup is not None
        assert en_lookup.id == memo.id

        # Cache-Trennung: DE-Pfad ist leer (kein EN-Memo durch DE-Lookup)
        de_lookup = await service.get_memo(ids["stock_id"], ids["run_id"], language="de")
        assert de_lookup is None


async def test_pydantic_fail_persists_error_memo(
    seeded_run_with_stock: tuple[async_sessionmaker[AsyncSession], dict[str, UUID]],
) -> None:
    """Pydantic-Fail-Pfad: malformed_response → Error-Memo mit confidence=low."""
    session_factory, ids = seeded_run_with_stock

    stub = StubAnthropicClient([FIXTURES / "malformed_response.json"])
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session_factory),
        pricing=PRICING,
        cap_usd=Decimal("20"),
    )
    async with session_factory() as session:
        service = NarrativeService(
            memo_repository=SQLAResearchMemoRepository(session_factory),
            run_repository=SQLARankingRunRepository(session),
            stock_repository=SQLAStockRepository(session),
            batch_repository=SQLAMemoBatchJobRepository(session_factory),
            llm_client=LLMClient(
                anthropic=stub,
                voyage=None,
                cost_tracker=cost_tracker,
                pricing=PRICING,
            ),
            prompt_loader=PromptTemplateLoader(),
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            stock_repo_factory=lambda s: SQLAStockRepository(session=s),
            run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
        )

        memo = await service.generate_memo(ids["stock_id"], ids["run_id"])

    assert memo.confidence == "low"
    assert memo.model_version == "error-fallback"


async def test_cache_hit_smoke_two_sequential_calls(
    seeded_run_with_stock: tuple[async_sessionmaker[AsyncSession], dict[str, UUID]],
) -> None:
    """Smoke: 2 generate_memo-Calls → Stub-Client sieht 2x denselben System-Block."""
    session_factory, ids = seeded_run_with_stock
    second_stock_id = ids["second_stock_id"]

    stub = StubAnthropicClient(
        [
            FIXTURES / "top_quality_stock.json",
            FIXTURES / "contradictory_quality_risk.json",
        ]
    )
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session_factory),
        pricing=PRICING,
        cap_usd=Decimal("20"),
    )
    async with session_factory() as session:
        service = NarrativeService(
            memo_repository=SQLAResearchMemoRepository(session_factory),
            run_repository=SQLARankingRunRepository(session),
            stock_repository=SQLAStockRepository(session),
            batch_repository=SQLAMemoBatchJobRepository(session_factory),
            llm_client=LLMClient(
                anthropic=stub,
                voyage=None,
                cost_tracker=cost_tracker,
                pricing=PRICING,
            ),
            prompt_loader=PromptTemplateLoader(),
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            stock_repo_factory=lambda s: SQLAStockRepository(session=s),
            run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
        )

        await service.generate_memo(ids["stock_id"], ids["run_id"])
        await service.generate_memo(second_stock_id, ids["run_id"])

    assert len(stub.messages.calls) == 2
    sys1 = stub.messages.calls[0]["system"]
    sys2 = stub.messages.calls[1]["system"]
    assert sys1 == sys2
    assert sys1[0]["cache_control"] == {"type": "ephemeral"}
