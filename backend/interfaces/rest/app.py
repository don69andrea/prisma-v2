"""FastAPI Application-Factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.config import get_settings
from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.exception_handlers import handle_budget_cap_exceeded
from backend.interfaces.rest.routers import (
    admin,
    backtests,
    decision_audit,
    decisions,
    eligibility,
    fonds_vergleich,
    health,
    macro,
    memos,
    ml,
    news,
    portfolio,
    rag,
    rebalancing,
    runs,
    steuer,
    stocks,
    universes,
)

_logger = logging.getLogger(__name__)


def _build_scheduler() -> AsyncIOScheduler:
    """Erzeugt einen APScheduler für tägliche News-Ingestion (07:00 Europe/Zurich)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from backend.infrastructure.adapters.rss_news_adapter import RssNewsAdapter
    from backend.infrastructure.adapters.ticker_ner import SWISS_TICKERS, TickerNer
    from backend.infrastructure.llm.client import LLMClient
    from backend.infrastructure.llm.pricing import PRICING
    from backend.infrastructure.persistence.repositories.news_repository import (
        SQLANewsRepository,
    )
    from backend.infrastructure.persistence.session import get_session_factory

    scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone="Europe/Zurich")

    async def _scheduled_ingest() -> None:
        from backend.application.services.cost_tracker import CostTracker
        from backend.application.services.news_ingestion_service import NewsIngestionService
        from backend.infrastructure.llm.pricing import PRICING as _pricing
        from backend.infrastructure.persistence.repositories.cost_log_repository import (
            SQLACostLogRepository,
        )

        cost_repo = SQLACostLogRepository(session_factory=get_session_factory())
        settings = get_settings()
        cost_tracker = CostTracker(
            repository=cost_repo,
            pricing=_pricing,
            cap_usd=settings.budget_cap_usd,
            threshold=settings.budget_cap_threshold,
        )
        import anthropic as _anthropic
        import voyageai as _voyageai

        voyage = (
            _voyageai.Client(api_key=settings.voyage_api_key)  # type: ignore[attr-defined]
            if settings.voyage_api_key
            else None
        )
        llm = LLMClient(
            anthropic=_anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key, timeout=30.0, max_retries=3
            ),
            voyage=voyage,
            cost_tracker=cost_tracker,
            pricing=PRICING,
        )
        svc = NewsIngestionService(
            news_repo=SQLANewsRepository(session_factory=get_session_factory()),
            rss_adapter=RssNewsAdapter(),
            ticker_ner=TickerNer(SWISS_TICKERS),
            llm_client=llm,
        )
        stats = await svc.ingest_all()
        _logger.info("Scheduled news ingestion complete: %s", stats)

    scheduler.add_job(_scheduled_ingest, "cron", hour=7, minute=0, id="daily_news_ingest")
    return scheduler


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler = _build_scheduler()
    scheduler.start()
    _logger.info("APScheduler started — daily news ingestion at 07:00 Europe/Zurich")
    yield
    scheduler.shutdown(wait=False)
    # On shutdown: mark any jobs that are still "running" or "pending" as failed
    # so the next restart can safely ignore them instead of treating them as active.
    try:
        from backend.infrastructure.persistence.repositories.memo_batch_job_repository import (
            SQLAMemoBatchJobRepository,
        )
        from backend.infrastructure.persistence.session import get_session_factory

        repo = SQLAMemoBatchJobRepository(session_factory=get_session_factory())
        now = datetime.now(tz=UTC)
        for status in ("running", "pending"):
            jobs = await repo.list_by_status(status)
            for job in jobs:
                await repo.save(
                    job.model_copy(
                        update={
                            "status": "failed",
                            "completed_at": now,
                            "error_message": "Aborted by server shutdown",
                        }
                    )
                )
            if jobs:
                _logger.warning("Shutdown: marked %d %s job(s) as failed", len(jobs), status)
    except Exception:
        _logger.exception("Shutdown cleanup failed — some jobs may remain in stale state")


def create_app() -> FastAPI:
    """Erzeugt und konfiguriert die FastAPI-Anwendung.

    Separate Factory-Funktion (statt Modul-Level-Instanz) ermöglicht saubere
    Test-Isolation: jeder Test kann create_app() mit überschriebenen Settings
    aufrufen ohne globalen State zu teilen.
    """
    settings = get_settings()

    app = FastAPI(
        lifespan=_lifespan,
        title="PRISMA API",
        description=(
            "Quantitatives Stock-Selection-Tool. "
            "Dieses Tool dient ausschliesslich zu Forschungs- und Bildungszwecken — "
            "keine Anlageberatung."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # FastAPI typisiert add_exception_handler über `Type[Exception]` mit einem
    # generischen Handler-Signature, das unsere konkrete (Request, BudgetCapExceeded)-
    # Signatur nicht akzeptiert. Laufzeit funktioniert korrekt; das ist ein
    # bekanntes Sticky-Problem im Starlette/FastAPI-Type-Stub.
    app.add_exception_handler(BudgetCapExceeded, handle_budget_cap_exceeded)  # type: ignore[arg-type]

    app.include_router(health.router)
    app.include_router(stocks.router)
    app.include_router(eligibility.router)
    app.include_router(universes.router)
    app.include_router(admin.router)
    app.include_router(runs.router)
    app.include_router(memos.router, prefix="/api/v1")
    app.include_router(backtests.router)
    app.include_router(rag.router)
    app.include_router(steuer.router)
    app.include_router(news.router)
    app.include_router(ml.router)
    app.include_router(decisions.router)
    app.include_router(decision_audit.router)
    app.include_router(macro.router)
    app.include_router(portfolio.router)
    app.include_router(fonds_vergleich.router)
    app.include_router(rebalancing.router)

    return app
