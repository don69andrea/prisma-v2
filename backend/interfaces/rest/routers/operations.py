"""REST Router: V4-6 Operations & Learning Loop API (read-only)."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Query

from backend.interfaces.rest.schemas.operations import PaperLogEntrySchema, PaperLogResponse

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
_logger = logging.getLogger(__name__)


@router.get("/paper-log", response_model=PaperLogResponse)
async def get_paper_log(
    coin: str | None = Query(None, description="Filter by coin (e.g. BTC-USD)"),
    since: date | None = Query(None, description="Filter entries since this date"),
    limit: int = Query(100, ge=1, le=1000),
) -> PaperLogResponse:
    """Gibt den Forward-Paper-Trading-Log zurück (append-only, Out-of-Sample).

    Read-only endpoint. Authentifizierung via X-API-Key Header erforderlich.
    """
    from backend.infrastructure.persistence.repositories.paper_trading_log_repository import (
        SQLAPaperTradingLogRepository,
    )
    from backend.infrastructure.persistence.session import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = SQLAPaperTradingLogRepository(session)
        entries = await repo.list_all(coin=coin, since=since)

    entries = entries[:limit]

    return PaperLogResponse(
        entries=[
            PaperLogEntrySchema(
                id=e.id,
                coin=e.coin,
                signal_date=e.signal_date,
                action=e.action,  # type: ignore[arg-type]
                size_factor=e.size_factor,
                confidence=e.confidence,
                pred_vol=e.pred_vol,
                realized_fwd_return=e.realized_fwd_return,
                written_at=e.written_at,
            )
            for e in entries
        ],
        total=len(entries),
    )
