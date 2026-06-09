"""REST Router: Fonds vs. Einzeltitel Vergleich."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.application.services.fonds_vergleich_service import (
    FondsNotFound,
    FondsVergleichService,
)
from backend.interfaces.rest.schemas.fonds_vergleich import (
    FondsVergleichRequest,
    FondsVergleichResponse,
    PortfolioMetricsResponse,
    ViacFondsItem,
)

router = APIRouter(prefix="/api/v1/fonds", tags=["fonds-vergleich"])
_logger = logging.getLogger(__name__)


def _get_service() -> FondsVergleichService:
    return FondsVergleichService()


@router.get(
    "",
    response_model=list[ViacFondsItem],
    summary="Verfügbare VIAC-Fonds auflisten",
)
async def list_fonds(service: FondsVergleichService = Depends(_get_service)) -> list[ViacFondsItem]:
    items = service.list_fonds()
    return [
        ViacFondsItem(
            name=str(item["name"]),
            description=str(item["description"]),
            equity_ratio=float(str(item["equity_ratio"])),
        )
        for item in items
    ]


@router.post(
    "/vergleich",
    response_model=FondsVergleichResponse,
    summary="VIAC-Fonds vs. Custom-Portfolio vergleichen",
    description=(
        "Vergleicht einen VIAC-Strategiefonds mit einem benutzerdefinierten "
        "Einzeltitel-Portfolio. Metriken: Expected Return, Volatility, Sharpe, Max Drawdown. "
        "⚠️ Historische Performance ≠ Zukunft. Keine Anlageberatung."
    ),
)
async def compare_fonds(
    body: FondsVergleichRequest,
    service: FondsVergleichService = Depends(_get_service),
) -> FondsVergleichResponse:
    try:
        result = await service.compare(
            fonds_name=body.fonds_name,
            positions=[{"ticker": p.ticker, "weight": p.weight} for p in body.positions],
            lookback_years=body.lookback_years,
        )
    except FondsNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FondsVergleichResponse(
        fonds_name=result.fonds_name,
        fonds_metrics=PortfolioMetricsResponse(
            expected_return_pa=result.fonds_metrics.expected_return_pa,
            volatility_pa=result.fonds_metrics.volatility_pa,
            sharpe_ratio=result.fonds_metrics.sharpe_ratio,
            max_drawdown=result.fonds_metrics.max_drawdown,
        ),
        custom_metrics=PortfolioMetricsResponse(
            expected_return_pa=result.custom_metrics.expected_return_pa,
            volatility_pa=result.custom_metrics.volatility_pa,
            sharpe_ratio=result.custom_metrics.sharpe_ratio,
            max_drawdown=result.custom_metrics.max_drawdown,
        ),
        snapshot_date=result.snapshot_date,
        disclaimer=result.disclaimer,
    )
