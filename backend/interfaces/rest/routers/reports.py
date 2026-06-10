"""REST Router: PDF Report Generator — GET /api/v1/stocks/{ticker}/report.pdf"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from backend.application.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/stocks", tags=["reports"])
_logger = logging.getLogger(__name__)


@router.get(
    "/{ticker}/report.pdf",
    summary="PDF Institutional Report für einen Ticker",
    description=(
        "Generiert einen professionellen Investment-Report als PDF (A4, Dark Theme). "
        "Aggregiert: Quant-Scores, ML-Prediction + SHAP, Fundamentaldaten, Narrative. "
        "Redis-gecacht für 6h. Keine Anlageberatung."
    ),
    response_class=Response,
)
async def get_report(ticker: str) -> Response:
    svc = ReportService()
    try:
        pdf_bytes = await svc.generate_pdf(ticker.upper())
    except Exception as exc:
        _logger.exception("PDF-Generierung fehlgeschlagen für %s", ticker)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF-Generierung fehlgeschlagen.",
        ) from exc

    filename = f"PRISMA_{ticker.upper()}_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
