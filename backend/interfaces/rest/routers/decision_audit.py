"""REST Router: Decision Audit Trail — GET + POST /api/v1/decisions/{ticker}/audit."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.decision_audit_service import DecisionAuditService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.infrastructure.persistence.repositories.decision_audit_repository import (
    SQLADecisionAuditRepository,
)
from backend.interfaces.rest.dependencies import (
    get_session,
    get_swiss_stock_repository,
)
from backend.interfaces.rest.schemas.decision_audit import (
    DecisionAuditListResponse,
    DecisionAuditRecordResponse,
)

router = APIRouter(prefix="/api/v1/decisions", tags=["decision-audit"])
_logger = logging.getLogger(__name__)


def get_audit_service(
    session: AsyncSession = Depends(get_session),
    swiss_repo: SwissStockRepository = Depends(get_swiss_stock_repository),
) -> DecisionAuditService:
    return DecisionAuditService(
        audit_repo=SQLADecisionAuditRepository(session=session),
        swiss_stock_repo=swiss_repo,
    )


@router.get(
    "/{ticker}/audit",
    response_model=DecisionAuditListResponse,
    summary="Audit Trail für einen Ticker",
    description=(
        "Gibt die letzten Entscheidungen (BUY/HOLD/WATCH) mit vollständiger "
        "Begründung zurück — Quant-Score, ML-Signal, Makro-Score, Gewichtung."
    ),
)
async def get_audit_trail(
    ticker: str = Path(..., pattern=r"^[A-Z0-9.\-]{1,12}$"),
    limit: int = Query(default=10, ge=1, le=50),
    service: DecisionAuditService = Depends(get_audit_service),
) -> DecisionAuditListResponse:
    records = await service.get_audit_trail(ticker.upper(), limit=limit)
    return DecisionAuditListResponse(
        ticker=ticker.upper(),
        records=[
            DecisionAuditRecordResponse(
                id=r.id,
                ticker=r.ticker,
                signal=r.signal,
                weighted_score=r.weighted_score,
                quant_score=r.quant_score,
                ml_score=r.ml_score,
                macro_score=r.macro_score,
                is_3a_eligible=r.is_3a_eligible,
                snapshot_date=r.snapshot_date,
                computed_at=r.computed_at,
                explanation_de=r.explanation_de,
            )
            for r in records
        ],
        total=len(records),
    )


@router.post(
    "/{ticker}/audit",
    response_model=DecisionAuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Signal berechnen und Audit-Record speichern",
    description=(
        "Berechnet das aktuelle BUY/HOLD/WATCH-Signal für einen Ticker "
        "und persistiert den vollständigen Audit-Record inkl. Begründung."
    ),
)
async def compute_and_save_audit(
    ticker: str = Path(..., pattern=r"^[A-Z0-9.\-]{1,12}$"),
    service: DecisionAuditService = Depends(get_audit_service),
) -> DecisionAuditRecordResponse:
    try:
        record = await service.compute_and_save(ticker.upper())
    except Exception as exc:
        _logger.exception("Audit-Berechnung fehlgeschlagen für %s", ticker)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signal-Berechnung fehlgeschlagen.",
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Marktdaten für '{ticker.upper()}'.",
        )

    return DecisionAuditRecordResponse(
        id=record.id,
        ticker=record.ticker,
        signal=record.signal,
        weighted_score=record.weighted_score,
        quant_score=record.quant_score,
        ml_score=record.ml_score,
        macro_score=record.macro_score,
        is_3a_eligible=record.is_3a_eligible,
        snapshot_date=record.snapshot_date,
        computed_at=record.computed_at,
        explanation_de=record.explanation_de,
    )
