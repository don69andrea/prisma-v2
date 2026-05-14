"""E2E-Integration-Test: POST /memos/batch -> Polling bis complete -> Memos in DB.

Spec: docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md §6.
Benoetigt eine laufende Postgres-Instanz (pytest.mark.integration).
Wird in CI uebersprungen wenn DB nicht erreichbar.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
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
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_narrative_service
from backend.tests.fixtures.llm.stub_anthropic_client import StubAnthropicClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / "narrative"

# Mini-Universe: 3 Stocks (NESN rank 1, ROG rank 2, ABBN rank 3)
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


class _BatchFlowContext:
    """Traegt seed-IDs durch den Test."""

    run_id: UUID
    stock_ids: dict[str, UUID]  # ticker -> stock_id


@pytest_asyncio.fixture
async def integration_db_with_stocks_and_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[_BatchFlowContext, None]:
    """3 Stocks + Universe + RankingRun in DB.

    Wird nach dem Test bereinigt (TRUNCATE CASCADE).
    """
    ctx = _BatchFlowContext()
    ctx.run_id = uuid4()
    ctx.stock_ids = {
        "NESN": uuid4(),
        "ROG": uuid4(),
        "ABBN": uuid4(),
    }
    universe_id = uuid4()

    truncate_sql = text(
        "TRUNCATE research_memos, memo_batch_jobs, llm_call_log, "
        "ranking_runs, universes, stocks CASCADE"
    )

    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()

        for ticker, sid in ctx.stock_ids.items():
            await session.execute(
                text(
                    "INSERT INTO stocks (id, ticker, name, currency) "
                    "VALUES (:id, :ticker, :name, 'CHF')"
                ),
                {"id": sid, "ticker": ticker, "name": ticker},
            )

        await session.execute(
            text(
                "INSERT INTO universes (id, name, region, tickers) "
                "VALUES (:id, 'TEST', 'CH', ARRAY['NESN', 'ROG', 'ABBN']::varchar[])"
            ),
            {"id": universe_id},
        )

        results_json = json.dumps(_SAMPLE_RESULTS)
        await session.execute(
            text(
                "INSERT INTO ranking_runs "
                "  (id, universe_id, status, weight_config, results, created_at) "
                "VALUES (:id, :uid, 'completed', '{}', cast(:results as jsonb), now())"
            ),
            {"id": ctx.run_id, "uid": universe_id, "results": results_json},
        )
        await session.commit()

    yield ctx

    async with session_factory() as session:
        await session.execute(truncate_sql)
        await session.commit()


async def test_batch_top_n_full_flow(
    integration_db_with_stocks_and_run: _BatchFlowContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """POST /batch top_n=3 -> Polling bis status=complete -> 3 memos mit Tickers."""
    ctx = integration_db_with_stocks_and_run

    # StubAnthropicClient mit 3 Fixtures (eine pro Stock)
    stub = StubAnthropicClient(
        [
            _FIXTURES / "top_quality_stock.json",
            _FIXTURES / "contradictory_quality_risk.json",
            _FIXTURES / "top_quality_stock.json",  # dritter Stock — drittes Fixture
        ]
    )
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session_factory),
        pricing=PRICING,
        cap_usd=Decimal("50"),
    )
    # Request-scoped run/stock-Repos sind hier Stubs (__new__) — start_batch
    # nutzt die Factory + session_factory fuer Run-Validation; Worker macht
    # eigene Sessions ueber die Factories. Damit ist der Service Background-
    # tauglich auch ohne lebende Request-Session.
    service = NarrativeService(
        memo_repository=SQLAResearchMemoRepository(session_factory),
        run_repository=SQLARankingRunRepository.__new__(SQLARankingRunRepository),
        stock_repository=SQLAStockRepository.__new__(SQLAStockRepository),
        batch_repository=SQLAMemoBatchJobRepository(session_factory),
        llm_client=LLMClient(
            anthropic=stub, voyage=None, cost_tracker=cost_tracker, pricing=PRICING
        ),
        prompt_loader=PromptTemplateLoader(),
        cost_tracker=cost_tracker,
        session_factory=session_factory,
        # Factories fuer Background-Worker-Repos (PR #70 W4 — Hexagonal).
        stock_repo_factory=lambda s: SQLAStockRepository(session=s),
        run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
    )

    app = create_app()
    app.dependency_overrides[get_narrative_service] = lambda: service

    # AsyncClient statt TestClient: vermeidet anyio-Thread-Hopping, das mit
    # async session_factory + asyncio.gather in _execute_batch zu Event-Loop-
    # Mismatch fuehren wuerde ("Future attached to a different loop").
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # POST /batch
        resp = await client.post(
            "/api/v1/memos/batch",
            json={
                "model_run_id": str(ctx.run_id),
                "top_n": 3,
                "language": "de",
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        # Polling bis status terminal (max 30s)
        body = None
        for _ in range(30):
            await asyncio.sleep(1)
            poll = await client.get(f"/api/v1/memos/jobs/{job_id}")
            assert poll.status_code == 200
            body = poll.json()
            if body["status"] in ("complete", "partial", "failed"):
                break
        else:
            pytest.fail("Job did not finish in 30s")

    app.dependency_overrides.clear()

    assert body is not None
    assert body["status"] == "complete"
    assert body["progress"]["completed"] == 3
    assert body["progress"]["failed"] == 0
    assert len(body["memos"]) == 3
    for memo in body["memos"]:
        assert memo["ticker"] is not None, f"ticker ist None fuer stock_id={memo['stock_id']}"
        assert memo["ticker"] != ""
        assert memo["is_error"] is False
