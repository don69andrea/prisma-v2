"""REST Router: ML Prediction API — POST /api/v1/ml/predict."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.application.services.ml_prediction_service import MLPredictionService
from backend.interfaces.rest.schemas.ml_predict import MLPredictRequest, MLPredictResponse

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])
_logger = logging.getLogger(__name__)


def get_ml_prediction_service() -> MLPredictionService:
    return MLPredictionService()


@router.post(
    "/predict",
    response_model=MLPredictResponse,
    summary="ML Return-Prediction für einen Swiss Ticker",
    description=(
        "Berechnet aktuelle Features (yfinance) und gibt eine 3-Klassen-Vorhersage "
        "zurück: UNDERPERFORM / NEUTRAL / OUTPERFORM (12M-Forward-Return Quartil). "
        "Erfordert ein trainiertes Modell-Artifact in models/. "
        "Gibt 503 zurück wenn kein Modell vorhanden, 404 wenn keine Marktdaten verfügbar."
    ),
)
async def predict(
    req: MLPredictRequest,
    service: MLPredictionService = Depends(get_ml_prediction_service),
) -> MLPredictResponse:
    try:
        result = await service.predict(req.ticker)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        _logger.exception("Fehler bei ML-Prediction für %s", req.ticker)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interner Fehler bei der ML-Prediction.",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Marktdaten verfügbar für Ticker '{req.ticker}'.",
        )

    return MLPredictResponse(
        ticker=result.ticker,
        snapshot_date=result.snapshot_date,
        predicted_class=result.predicted_class,
        signal=result.signal,
        prob_bottom=result.prob_bottom,
        prob_mid=result.prob_mid,
        prob_top=result.prob_top,
        confidence=result.confidence,
        model_type=result.model_type,
        features=result.features,
    )
