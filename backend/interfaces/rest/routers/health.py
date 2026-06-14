"""Health-Check-Endpunkt — wird von Load-Balancern und Docker HEALTHCHECK genutzt."""

import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.infrastructure.persistence.session import get_session_factory

router = APIRouter(tags=["health"])

_VERSION = os.environ.get("APP_VERSION", "2.0.0")
_logger = logging.getLogger(__name__)


@router.get("/health", summary="Liveness probe")
async def health() -> JSONResponse:
    """Gibt HTTP 200 mit status + version zurück wenn die App läuft."""
    return JSONResponse({"status": "ok", "version": _VERSION})


@router.get("/health/ready", summary="Readiness probe — prüft DB-Konnektivität")
async def health_ready() -> JSONResponse:
    """Readiness probe: gibt 200 wenn DB erreichbar, 503 sonst."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return JSONResponse({"ready": True, "database": "ok"})
    except Exception as exc:
        _logger.warning("Readiness-Check fehlgeschlagen: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database nicht erreichbar: {exc}") from exc
