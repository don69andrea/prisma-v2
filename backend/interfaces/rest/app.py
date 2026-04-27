"""FastAPI Application-Factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.exception_handlers import handle_budget_cap_exceeded
from backend.interfaces.rest.routers import admin, health, runs, stocks


def create_app() -> FastAPI:
    """Erzeugt und konfiguriert die FastAPI-Anwendung.

    Separate Factory-Funktion (statt Modul-Level-Instanz) ermöglicht saubere
    Test-Isolation: jeder Test kann create_app() mit überschriebenen Settings
    aufrufen ohne globalen State zu teilen.
    """
    settings = get_settings()

    app = FastAPI(
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
    app.include_router(admin.router)
    app.include_router(runs.router)

    return app
