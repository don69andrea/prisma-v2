"""Health-Check-Endpunkt — wird von Load-Balancern und Docker HEALTHCHECK genutzt."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.persistence.repositories.cron_run_repository import (
    SQLACronRunRepository,
)
from backend.infrastructure.persistence.session import get_session_factory
from backend.interfaces.rest.dependencies import get_session

router = APIRouter(tags=["health"])

_VERSION = os.environ.get("APP_VERSION", "2.1.0")
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


@router.get("/health/pipeline")
async def pipeline_health(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Letzter Run-Status pro Cron-Job."""
    repo = SQLACronRunRepository(session)
    records = await repo.get_latest_per_job()
    return [
        {
            "job": r.job_name,
            "status": r.status,
            "last_run": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "records_saved": r.records_saved,
            "error": r.error_msg,
        }
        for r in records
    ]
