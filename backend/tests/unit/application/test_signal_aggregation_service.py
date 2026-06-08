"""Unit-Tests für SignalAggregationService."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from backend.application.services.signal_aggregation_service import (
    SignalAggregationService,
    _is_3a_eligible,
    _snb_macro_score,
)
from backend.domain.value_objects.decision_signal import DecisionSignal
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector
from backend.domain.value_objects.ml_prediction import MLPrediction


def _make_features(
    ticker: str = "NESN",
    quant_score: float = 72.0,
    snb_rate: float = 0.25,
) -> MLFeatureVector:
    return MLFeatureVector(
        ticker=ticker,
        snapshot_date=date(2024, 6, 1),
        quant_score=quant_score,
        score_rendite=60.0,
        score_sicherheit=70.0,
        score_wachstum=60.0,
        score_substanz=65.0,
        return_12m=0.10,
        vol_30d=0.15,
        rsi_14=55.0,
        snb_rate=snb_rate,
        chf_eur=0.93,
        forward_return_12m=None,
        target_class=None,
    )


def _make_prediction(signal: str = "OUTPERFORM") -> MLPrediction:
    return MLPrediction(
        ticker="NESN",
        snapshot_date=date(2024, 6, 1),
        predicted_class=2,
        signal=signal,
        prob_bottom=0.1,
        prob_mid=0.2,
        prob_top=0.7,
        confidence=0.7,
        model_type="xgboost",
        features={},
    )


# --- _snb_macro_score ---


def test_snb_macro_score_very_low() -> None:
    assert _snb_macro_score(-0.5) == 80.0


def test_snb_macro_score_zero() -> None:
    assert _snb_macro_score(0.0) == 80.0


def test_snb_macro_score_accommodative() -> None:
    assert _snb_macro_score(0.25) == 65.0


def test_snb_macro_score_neutral() -> None:
    assert _snb_macro_score(0.75) == 50.0


def test_snb_macro_score_restrictive() -> None:
    assert _snb_macro_score(1.25) == 35.0


def test_snb_macro_score_very_restrictive() -> None:
    assert _snb_macro_score(2.0) == 20.0


# --- _is_3a_eligible ---


def test_3a_eligible_nesn() -> None:
    assert _is_3a_eligible("NESN") is True
    assert _is_3a_eligible("nesn") is True


def test_3a_not_eligible_unknown() -> None:
    assert _is_3a_eligible("UNKNOWN123") is False


# --- SignalAggregationService ---


@pytest.mark.asyncio
async def test_get_signal_buy() -> None:
    """Hoher Quant + OUTPERFORM ML → BUY."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_features(quant_score=80.0, snb_rate=0.25)
    pred_svc = AsyncMock()
    pred_svc.predict.return_value = _make_prediction("OUTPERFORM")

    service = SignalAggregationService(
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    result = await service.get_signal("NESN")

    assert result is not None
    assert result.signal == "BUY"
    assert result.ticker == "NESN"
    assert result.is_3a_eligible is True
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_get_signal_watch() -> None:
    """Niedriger Quant + UNDERPERFORM ML + restriktive SNB → WATCH."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_features(quant_score=20.0, snb_rate=2.0)
    pred_svc = AsyncMock()
    pred_svc.predict.return_value = _make_prediction("UNDERPERFORM")

    service = SignalAggregationService(
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    result = await service.get_signal("NESN")

    assert result is not None
    assert result.signal == "WATCH"


@pytest.mark.asyncio
async def test_get_signal_hold_mid_values() -> None:
    """Mittlere Werte → HOLD."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_features(quant_score=50.0, snb_rate=0.75)
    pred_svc = AsyncMock()
    pred_svc.predict.return_value = _make_prediction("NEUTRAL")

    service = SignalAggregationService(
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    result = await service.get_signal("NOVN")

    assert result is not None
    assert result.signal == "HOLD"


@pytest.mark.asyncio
async def test_get_signal_no_features_returns_none() -> None:
    """Keine Marktdaten → None."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = None
    pred_svc = AsyncMock()

    service = SignalAggregationService(
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    result = await service.get_signal("UNKNOWN")
    assert result is None


@pytest.mark.asyncio
async def test_get_signal_no_ml_model_fallback_neutral() -> None:
    """Kein ML-Modell → Fallback auf NEUTRAL (50), trotzdem ein Signal."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_features(quant_score=72.0, snb_rate=0.25)
    pred_svc = AsyncMock()
    pred_svc.predict.side_effect = FileNotFoundError("kein Modell")

    service = SignalAggregationService(
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    result = await service.get_signal("NESN")

    assert result is not None
    assert result.ml_score == 50.0
    assert result.signal in {"BUY", "HOLD", "WATCH"}


@pytest.mark.asyncio
async def test_get_signals_skips_failed() -> None:
    """get_signals überspringt Ticker mit Exception."""
    feature_svc = AsyncMock()
    feature_svc.build_features.side_effect = [
        _make_features("NESN", quant_score=75.0),
        RuntimeError("API timeout"),
        _make_features("ROG", quant_score=60.0),
    ]
    pred_svc = AsyncMock()
    pred_svc.predict.return_value = _make_prediction("NEUTRAL")

    service = SignalAggregationService(
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    results = await service.get_signals(["NESN", "BADF", "ROG"])

    assert len(results) == 2
    tickers = {r.ticker for r in results}
    assert tickers == {"NESN", "ROG"}


def test_decision_signal_for_score() -> None:
    assert DecisionSignal.signal_for_score(70.0) == "BUY"
    assert DecisionSignal.signal_for_score(65.0) == "BUY"
    assert DecisionSignal.signal_for_score(64.9) == "HOLD"
    assert DecisionSignal.signal_for_score(40.0) == "HOLD"
    assert DecisionSignal.signal_for_score(39.9) == "WATCH"
    assert DecisionSignal.signal_for_score(0.0) == "WATCH"
