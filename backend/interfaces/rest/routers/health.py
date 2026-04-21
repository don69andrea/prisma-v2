"""Health-Check-Endpunkt — wird von Load-Balancern und Docker HEALTHCHECK genutzt."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> JSONResponse:
    """Gibt HTTP 200 mit {"status": "ok"} zurück wenn die App läuft."""
    return JSONResponse({"status": "ok"})
