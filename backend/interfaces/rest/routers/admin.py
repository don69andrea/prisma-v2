"""Admin-Router: GET /api/v1/admin/costs — LLM-Kosten-Übersicht."""

from fastapi import APIRouter, Depends, Query

from backend.application.services.cost_tracker import CostTracker
from backend.interfaces.rest.dependencies import get_cost_tracker, require_admin_api_key
from backend.interfaces.rest.schemas.cost_summary import CostSummaryResponse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get(
    "/costs",
    response_model=CostSummaryResponse,
    summary="Aktuelle LLM-Kosten dieses Monats",
    description="Liefert Gesamtkosten, Aufschlüsselung nach Modell/Feature und letzte N Calls.",
)
async def get_costs(
    last: int = Query(default=10, ge=1, le=100, description="Anzahl letzter Calls"),
    _auth: None = Depends(require_admin_api_key),
    tracker: CostTracker = Depends(get_cost_tracker),
) -> CostSummaryResponse:
    summary = await tracker.summary(last_n=last)
    return CostSummaryResponse.from_cost_summary(summary)
