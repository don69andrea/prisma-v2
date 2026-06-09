"""Health-Check-Endpunkt — wird von Load-Balancern und Docker HEALTHCHECK genutzt."""

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

_VERSION = os.environ.get("APP_VERSION", "2.0.0")


@router.get("/health", summary="Liveness probe")
async def health() -> JSONResponse:
    """Gibt HTTP 200 mit status + version zurück wenn die App läuft."""
    return JSONResponse({"status": "ok", "version": _VERSION})
