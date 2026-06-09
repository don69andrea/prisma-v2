"""REST Router: Macro Intelligence API — GET /api/v1/macro/context."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.application.services.macro_service import MacroService
from backend.interfaces.rest.dependencies import get_llm_client
from backend.interfaces.rest.schemas.macro import MacroContextResponse

router = APIRouter(prefix="/api/v1/macro", tags=["macro"])
_logger = logging.getLogger(__name__)


def get_macro_service(
    llm_client: object = Depends(get_llm_client),
) -> MacroService:
    return MacroService(llm_client=llm_client)


@router.get(
    "/context",
    response_model=MacroContextResponse,
    summary="Aktueller Makro-Kontext Schweiz",
    description=(
        "Liefert SNB-Leitzins, CHF/EUR-Kurs und das Makro-Klima "
        "(EXPANSIV / NEUTRAL / RESTRIKTIV) inkl. kurzer LLM-Narrative (DE + EN). "
        "SNB-Daten via data.snb.ch mit Fallback auf hardcodierte Historie."
    ),
)
async def get_macro_context(
    service: MacroService = Depends(get_macro_service),
) -> MacroContextResponse:
    try:
        ctx = await service.get_context()
    except Exception as exc:
        _logger.exception("Fehler beim Abrufen des Makro-Kontexts")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Makro-Daten vorübergehend nicht verfügbar.",
        ) from exc

    return MacroContextResponse(
        leitzins=ctx.leitzins,
        chf_eur=ctx.chf_eur,
        inflation_ch=ctx.inflation_ch,
        pmi_ch=ctx.pmi_ch,
        snapshot_date=ctx.snapshot_date,
        climate=ctx.climate,
        narrative_de=ctx.narrative_de,
        narrative_en=ctx.narrative_en,
    )
