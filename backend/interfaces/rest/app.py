"""FastAPI Application-Factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.dependencies import require_admin_api_key
from backend.interfaces.rest.exception_handlers import (
    handle_budget_cap_exceeded,
    handle_unhandled_exception,
)
from backend.interfaces.rest.rate_limiter import LLMRateLimiterMiddleware
from backend.interfaces.rest.routers import (
    admin,
    alerts,
    backtests,
    chat,
    decision_audit,
    decisions,
    discovery,
    dividends,
    eligibility,
    fonds_vergleich,
    fundamentals,
    health,
    macro,
    memos,
    ml,
    news,
    portfolio,
    rag,
    rebalancing,
    reports,
    runs,
    signals,
    steuer,
    stocks,
    universes,
)

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from backend.infrastructure.workers.alert_worker import create_alert_scheduler

    try:
        scheduler = create_alert_scheduler()
        scheduler.start()
        _logger.info("APScheduler started — daily alert check at 08:00 Europe/Zurich")
    except Exception:
        _logger.exception("Alert-Scheduler konnte nicht gestartet werden — Alerts deaktiviert")
        scheduler = None
    yield
    if scheduler is not None:
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

    is_production = settings.environment == "production"
    app = FastAPI(
        lifespan=_lifespan,
        title="PRISMA API",
        description=(
            "Quantitatives Stock-Selection-Tool. "
            "Dieses Tool dient ausschliesslich zu Forschungs- und Bildungszwecken — "
            "keine Anlageberatung."
        ),
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # K-13: In Starlette the last-added middleware becomes the outermost layer.
    # LLMRateLimiterMiddleware must be added first (innermost) so that CORSMiddleware
    # (outermost) can attach CORS headers to 429 responses from the rate limiter.
    app.add_middleware(LLMRateLimiterMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # FastAPI typisiert add_exception_handler über `Type[Exception]` mit einem
    # generischen Handler-Signature, das unsere konkrete (Request, BudgetCapExceeded)-
    # Signatur nicht akzeptiert. Laufzeit funktioniert korrekt; das ist ein
    # bekanntes Sticky-Problem im Starlette/FastAPI-Type-Stub.
    app.add_exception_handler(BudgetCapExceeded, handle_budget_cap_exceeded)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unhandled_exception)

    _auth = [Depends(require_admin_api_key)]

    # Public — kein API-Key erforderlich
    app.include_router(health.router)  # Render health checks
    app.include_router(discovery.router)  # Onboarding-Flow (Demo, öffentlich)

    # Geschützt — X-API-Key Header erforderlich
    app.include_router(chat.router, dependencies=_auth)
    app.include_router(reports.router, dependencies=_auth)
    app.include_router(stocks.router, dependencies=_auth)
    app.include_router(eligibility.router, dependencies=_auth)
    app.include_router(dividends.router, dependencies=_auth)
    app.include_router(fundamentals.router, dependencies=_auth)
    app.include_router(universes.router, dependencies=_auth)
    app.include_router(admin.router, dependencies=_auth)
    app.include_router(runs.router, dependencies=_auth)
    app.include_router(memos.router, dependencies=_auth, prefix="/api/v1")
    app.include_router(backtests.router, dependencies=_auth)
    app.include_router(backtests.signal_router, dependencies=_auth)
    app.include_router(rag.router, dependencies=_auth)
    app.include_router(steuer.router, dependencies=_auth)
    app.include_router(news.router, dependencies=_auth)
    app.include_router(ml.router, dependencies=_auth)
    app.include_router(decisions.router, dependencies=_auth)
    app.include_router(decision_audit.router, dependencies=_auth)
    app.include_router(macro.router, dependencies=_auth)
    app.include_router(portfolio.router, dependencies=_auth)
    app.include_router(fonds_vergleich.router, dependencies=_auth)
    app.include_router(rebalancing.router, dependencies=_auth)
    app.include_router(alerts.router, dependencies=_auth)
    app.include_router(signals.router, dependencies=_auth)
    app.include_router(signals.backtest_router, dependencies=_auth)
    app.include_router(signals.agent_router, dependencies=_auth)

    return app
