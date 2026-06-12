"""FastAPI Exception-Handler für Domain-Exceptions.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §8.

Übersetzt domain-Exceptions in strukturierte HTTP-Responses mit
hilfreichen Headers (z.B. `Retry-After`).
"""

from datetime import UTC, datetime

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.domain.errors import BudgetCapExceeded


def _seconds_until_next_month_utc() -> int:
    """Sekunden bis zum 1. des nächsten Monats um 00:00 UTC.

    Wird als Wert für den `Retry-After`-Header genutzt — Clients können so
    transparent erkennen, wann das Cap zurückgesetzt wird.
    """
    now = datetime.now(UTC)
    if now.month == 12:
        next_month_start = now.replace(
            year=now.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        next_month_start = now.replace(
            month=now.month + 1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    delta = next_month_start - now
    return int(delta.total_seconds())


async def handle_unhandled_exception(
    request: Request,  # noqa: ARG001
    exc: Exception,
) -> JSONResponse:
    """Globaler Fallback — stellt sicher dass CORS-Header auch bei 500 vorhanden sind.

    FastAPI/Starlette's CORSMiddleware fügt keine Headers hinzu wenn eine
    unbehandelte Exception vor der Response-Phase auftritt. Dieser Handler
    wandelt alle unerwarteten Exceptions in eine JSON-Response mit
    Access-Control-Allow-Origin: * um, damit der Browser den Body sehen kann.
    """
    import logging
    logging.getLogger(__name__).exception("Unhandled exception in request %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        headers={"Access-Control-Allow-Origin": "*"},
        content={"detail": "Interner Serverfehler. Bitte später erneut versuchen."},
    )


async def handle_budget_cap_exceeded(
    request: Request,  # noqa: ARG001 — FastAPI-Handler-Signatur erfordert request
    exc: BudgetCapExceeded,
) -> JSONResponse:
    """`BudgetCapExceeded` → HTTP 402 mit strukturiertem JSON-Body.

    Status 402 (Payment Required) ist semantisch eng, signalisiert aber
    konsistent ueber alle AI-Endpoints (POST /memos/generate, POST /memos/batch)
    dieselbe Quota-Erschoepfung. `Retry-After`-Header gibt den Reset-Zeitpunkt.
    Vorher: 503 (Service Unavailable) — inkonsistent mit /memos/batch das
    bereits 402 lieferte; Diskussion siehe PR #70 W2.
    """
    return JSONResponse(
        status_code=402,
        headers={"Retry-After": str(_seconds_until_next_month_utc())},
        content={
            "error": "budget_cap_exceeded",
            "message": ("Monatliches AI-Budget erschöpft. Reset am 1. des nächsten Monats."),
            "current_usd": float(exc.current_usd),
            "cap_usd": float(exc.cap_usd),
        },
    )
