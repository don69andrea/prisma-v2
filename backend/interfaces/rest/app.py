"""FastAPI Application-Factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.exception_handlers import handle_budget_cap_exceeded
from backend.interfaces.rest.routers import (
    admin,
    backtests,
    eligibility,
    health,
    memos,
    rag,
    runs,
    steuer,
    stocks,
    universes,
)

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
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

    return app
