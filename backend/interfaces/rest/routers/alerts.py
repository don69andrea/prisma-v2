"""REST Router: Alert Engine — CRUD /api/v1/alerts."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.alert_service import AlertService
from backend.infrastructure.persistence.repositories.alert_repository import SQLAAlertRepository
from backend.interfaces.rest.dependencies import get_session
from backend.interfaces.rest.schemas.alert import (
    AlertCreateRequest,
    AlertListResponse,
    AlertResponse,
)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
_logger = logging.getLogger(__name__)


def _get_alert_service(session: AsyncSession = Depends(get_session)) -> AlertService:
    return AlertService(alert_repo=SQLAAlertRepository(session=session))


def _to_response(a: object) -> AlertResponse:
    from backend.domain.entities.alert import Alert

    assert isinstance(a, Alert)
    return AlertResponse(
        id=a.id,
        ticker=a.ticker,
        trigger_type=a.trigger_type,
        threshold=a.threshold,
        channel=a.channel,
        target=a.target,
        is_active=a.is_active,
        created_at=a.created_at,
        last_triggered_at=a.last_triggered_at,
        last_signal=a.last_signal,
        baseline_price=a.baseline_price,
    )


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alert erstellen",
)
async def create_alert(
    body: AlertCreateRequest,
    service: AlertService = Depends(_get_alert_service),
) -> AlertResponse:
    alert = await service.create_alert(
        ticker=body.ticker,
        trigger_type=body.trigger_type,
        threshold=body.threshold,
        channel=body.channel,
        target=body.target,
    )
    return _to_response(alert)


@router.get(
    "",
    response_model=AlertListResponse,
    summary="Alerts auflisten",
)
async def list_alerts(
    target: str | None = Query(default=None, description="Filter nach E-Mail/Webhook-Ziel"),
    service: AlertService = Depends(_get_alert_service),
) -> AlertListResponse:
    alerts = await service.list_alerts(target=target)
    return AlertListResponse(alerts=[_to_response(a) for a in alerts], total=len(alerts))


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alert löschen",
)
async def delete_alert(
    alert_id: UUID,
    service: AlertService = Depends(_get_alert_service),
) -> None:
    deleted = await service.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert nicht gefunden.")
