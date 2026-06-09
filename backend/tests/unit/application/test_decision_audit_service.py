"""Unit-Tests für DecisionAuditService."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.application.services.decision_audit_service import (
    DecisionAuditService,
    _build_explanation,
    _signal_for_score,
    _snb_macro_score,
)
from backend.domain.entities.decision_audit_record import DecisionAuditRecord
from backend.domain.entities.swiss_stock import SwissStock


def _make_feature_mock(quant_score: float = 72.0) -> MagicMock:
    """Simuliert den Rückgabewert von feature_service.build_features().
    Kein echter MLFeatureVector — dieser existiert erst nach Merge PR #42.
    """
    m = MagicMock()
    m.quant_score = quant_score
    m.snapshot_date = date(2024, 6, 1)
    return m


def _make_prediction_mock(signal: str = "OUTPERFORM") -> MagicMock:
    """Simuliert den Rückgabewert von prediction_service.predict().
    Kein echter MLPrediction — dieser existiert erst nach Merge PR #43.
    """
    m = MagicMock()
    m.signal = signal
    return m


def _make_stock(
    market_cap_chf: Decimal = Decimal("200_000_000"),
) -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker="NESN",
        isin="CH0012221716",
        name="Nestlé",
        exchange="XSWX",
        sector=None,
        market_cap_chf=market_cap_chf,
    )


# --- Hilfsfunktionen ---


def test_signal_for_score_thresholds() -> None:
    assert _signal_for_score(65.0) == "BUY"
    assert _signal_for_score(64.9) == "HOLD"
    assert _signal_for_score(40.0) == "HOLD"
    assert _signal_for_score(39.9) == "WATCH"


def test_snb_macro_score_values() -> None:
    assert _snb_macro_score(0.0) == 80.0
    assert _snb_macro_score(0.25) == 65.0
    assert _snb_macro_score(2.0) == 20.0


def test_build_explanation_contains_ticker_and_signal() -> None:
    text = _build_explanation(
        ticker="NESN",
        signal="BUY",
        weighted_score=72.5,
        quant_score=80.0,
        ml_score=85.0,
        macro_score=65.0,
        ml_signal="OUTPERFORM",
        is_3a_eligible=True,
    )
    assert "NESN" in text
    assert "BUY" in text
    assert "72.5" in text
    assert "3a-eligible" in text


# --- DecisionAuditService mit Feature/Prediction-Mocks ---


@pytest.mark.asyncio
async def test_compute_and_save_returns_record() -> None:
    """feature_service + prediction_service → vollständiger Audit-Record."""
    audit_repo = AsyncMock()
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_mock(quant_score=75.0)
    pred_svc = AsyncMock()
    pred_svc.predict.return_value = _make_prediction_mock("OUTPERFORM")

    service = DecisionAuditService(
        audit_repo=audit_repo,
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    record = await service.compute_and_save("NESN")

    assert record is not None
    assert record.ticker == "NESN"
    assert record.signal in {"BUY", "HOLD", "WATCH"}
    assert record.explanation_de != ""
    assert "NESN" in record.explanation_de
    audit_repo.save.assert_called_once_with(record)


@pytest.mark.asyncio
async def test_compute_and_save_no_features_no_repo_returns_none() -> None:
    """Weder feature_service noch swiss_stock_repo → None (keine Scores verfügbar)."""
    audit_repo = AsyncMock()
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = None

    service = DecisionAuditService(
        audit_repo=audit_repo,
        feature_service=feature_svc,
    )
    result = await service.compute_and_save("UNKNOWN")

    assert result is None
    audit_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_compute_and_save_ml_fallback_on_no_model() -> None:
    """Kein ML-Modell (FileNotFoundError) → ml_score=50 (NEUTRAL), trotzdem Record."""
    audit_repo = AsyncMock()
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_mock()
    pred_svc = AsyncMock()
    pred_svc.predict.side_effect = FileNotFoundError("kein Modell")

    service = DecisionAuditService(
        audit_repo=audit_repo,
        feature_service=feature_svc,
        prediction_service=pred_svc,
    )
    record = await service.compute_and_save("NESN")

    assert record is not None
    assert record.ml_score == 50.0
    audit_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_compute_and_save_3a_eligible_via_repo() -> None:
    """XSWX Large-Cap (200M CHF) + feature_service → is_3a_eligible=True."""
    audit_repo = AsyncMock()
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_mock()
    pred_svc = AsyncMock()
    pred_svc.predict.return_value = _make_prediction_mock("NEUTRAL")
    swiss_repo = AsyncMock()
    swiss_repo.get_by_ticker.return_value = _make_stock()

    service = DecisionAuditService(
        audit_repo=audit_repo,
        feature_service=feature_svc,
        prediction_service=pred_svc,
        swiss_stock_repo=swiss_repo,
    )
    record = await service.compute_and_save("NESN")

    assert record is not None
    assert record.is_3a_eligible is True


@pytest.mark.asyncio
async def test_compute_and_save_no_ml_services_uses_quant_scorer() -> None:
    """Ohne ML-Services: swiss_stock_repo → SwissQuantScorer-Fallback (Score ~50)."""
    audit_repo = AsyncMock()
    swiss_repo = AsyncMock()
    swiss_repo.get_by_ticker.return_value = _make_stock()

    service = DecisionAuditService(
        audit_repo=audit_repo,
        swiss_stock_repo=swiss_repo,
        snb_rate=0.25,
    )
    record = await service.compute_and_save("NESN")

    assert record is not None
    assert record.ticker == "NESN"
    # Ohne Fundamentaldaten: composite=50.0, ml_score=50.0, macro_score=65.0
    # weighted = 0.45*50 + 0.35*50 + 0.20*65 = 22.5+17.5+13 = 53.0 → HOLD
    assert record.signal == "HOLD"
    assert record.ml_score == 50.0
    audit_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_get_audit_trail_delegates_to_repo() -> None:
    audit_repo = AsyncMock()
    existing = [
        DecisionAuditRecord(
            id=uuid4(),
            ticker="NESN",
            signal="BUY",
            weighted_score=72.0,
            quant_score=80.0,
            ml_score=85.0,
            macro_score=65.0,
            is_3a_eligible=True,
            snapshot_date=date(2024, 6, 1),
            computed_at=datetime.now(tz=UTC),
            explanation_de="Test.",
        )
    ]
    audit_repo.list_by_ticker.return_value = existing

    service = DecisionAuditService(audit_repo=audit_repo)
    result = await service.get_audit_trail("NESN", limit=5)

    audit_repo.list_by_ticker.assert_called_once_with("NESN", limit=5)
    assert result == existing
