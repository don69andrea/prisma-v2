"""Decision Audit Service — berechnet Signal und persistiert Audit-Record."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.application.services.stock_service import _normalize_ticker
from backend.domain.entities.decision_audit_record import DecisionAuditRecord
from backend.domain.repositories.decision_audit_repository import DecisionAuditRepository
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.services.swiss_quant_scorer import SwissQuantScorer
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

_logger = logging.getLogger(__name__)

_W_QUANT = 0.45
_W_ML = 0.35
_W_MACRO = 0.20

_ML_SIGNAL_TO_SCORE: dict[str, float] = {
    "OUTPERFORM": 85.0,
    "NEUTRAL": 50.0,
    "UNDERPERFORM": 15.0,
}


def _snb_macro_score(snb_rate: float) -> float:
    if snb_rate <= 0.0:
        return 80.0
    if snb_rate <= 0.5:
        return 65.0
    if snb_rate <= 1.0:
        return 50.0
    if snb_rate <= 1.5:
        return 35.0
    return 20.0


def _signal_for_score(score: float) -> str:
    if score >= 65.0:
        return "BUY"
    if score >= 40.0:
        return "HOLD"
    return "SELL"


def _build_explanation(
    ticker: str,
    signal: str,
    weighted_score: float,
    quant_score: float,
    ml_score: float,
    macro_score: float,
    ml_signal: str,
    is_3a_eligible: bool,
) -> str:
    eligible_str = "3a-eligible" if is_3a_eligible else "nicht 3a-eligible"
    return (
        f"{ticker} erhält Signal {signal} (gewichteter Score: {weighted_score:.1f}). "
        f"Quant-Score: {quant_score:.1f} (Gewicht 45%), "
        f"ML-Signal: {ml_signal} → Score {ml_score:.0f} (Gewicht 35%), "
        f"Makro-Score: {macro_score:.0f} (SNB-Leitzins, Gewicht 20%). "
        f"Titel ist {eligible_str}."
    )


class DecisionAuditService:
    """Berechnet ein BUY/HOLD/SELL-Signal und speichert den Audit-Record.

    ml_feature_service / ml_prediction_service sind optional (Any | None).
    Sind sie nicht verfügbar, wird ml_score=50 (NEUTRAL) als Fallback verwendet.
    Swiss-Quant-Score wird direkt via SwissQuantScorer berechnet wenn kein
    feature_service vorhanden.
    """

    def __init__(
        self,
        audit_repo: DecisionAuditRepository,
        swiss_stock_repo: SwissStockRepository | None = None,
        swiss_market_data: Any | None = None,
        feature_service: Any | None = None,
        prediction_service: Any | None = None,
        snb_rate: float = 0.25,
    ) -> None:
        self._audit_repo = audit_repo
        self._swiss_stock_repo = swiss_stock_repo
        self._swiss_market_data = swiss_market_data
        self._feature_service = feature_service
        self._prediction_service = prediction_service
        self._snb_rate = snb_rate
        self._eligibility = EligibilityFilter()
        self._scorer = SwissQuantScorer()

    async def compute_and_save(self, ticker: str) -> DecisionAuditRecord | None:
        """Berechnet Signal für ticker, speichert Audit-Record und gibt ihn zurück."""
        upper = _normalize_ticker(ticker)

        # Quant-Score: via feature_service (ML-Layer) oder direkter SwissQuantScorer
        quant_score, snapshot_date = await self._get_quant_score(upper)
        if quant_score is None:
            return None

        # ML-Score: optionaler feature_service + prediction_service
        ml_score = 50.0
        ml_signal = "NEUTRAL"
        if self._feature_service is not None and self._prediction_service is not None:
            try:
                prediction = await self._prediction_service.predict(upper)
                if prediction is not None:
                    ml_signal = prediction.signal
                    ml_score = _ML_SIGNAL_TO_SCORE.get(ml_signal, 50.0)
            except FileNotFoundError:
                pass
            except Exception:
                _logger.exception("ML-Prediction fehlgeschlagen für %s", upper)

        macro_score = _snb_macro_score(self._snb_rate)
        weighted_score = _W_QUANT * quant_score + _W_ML * ml_score + _W_MACRO * macro_score
        signal = _signal_for_score(weighted_score)
        is_eligible = await self._check_eligible(upper)

        explanation = _build_explanation(
            ticker=upper,
            signal=signal,
            weighted_score=round(weighted_score, 1),
            quant_score=round(quant_score, 1),
            ml_score=round(ml_score, 0),
            macro_score=round(macro_score, 0),
            ml_signal=ml_signal,
            is_3a_eligible=is_eligible,
        )

        record = DecisionAuditRecord(
            id=uuid4(),
            ticker=upper,
            signal=signal,
            weighted_score=round(weighted_score, 2),
            quant_score=round(quant_score, 2),
            ml_score=round(ml_score, 2),
            macro_score=round(macro_score, 2),
            is_3a_eligible=is_eligible,
            snapshot_date=snapshot_date,
            computed_at=datetime.now(tz=UTC),
            explanation_de=explanation,
        )
        await self._audit_repo.save(record)
        return record

    async def get_audit_trail(self, ticker: str, limit: int = 10) -> list[DecisionAuditRecord]:
        return await self._audit_repo.list_by_ticker(_normalize_ticker(ticker), limit=limit)

    async def _get_quant_score(self, ticker: str) -> tuple[float | None, Any]:
        today = datetime.now(tz=UTC).date()

        # Wenn feature_service vorhanden (ML-Layer PR): direkt nutzen
        if self._feature_service is not None:
            try:
                features = await self._feature_service.build_features(ticker)
                if features is not None:
                    return features.quant_score, features.snapshot_date
            except Exception:
                _logger.warning("feature_service fehlgeschlagen für %s", ticker)

        # Fallback: SwissQuantScorer über SwissStockRepository + MarketData
        if self._swiss_stock_repo is None:
            return None, today
        stock = await self._swiss_stock_repo.get_by_ticker(ticker)
        if stock is None:
            return None, today
        _empty = SwissFundamentals(
            market_cap_chf=None, pe_ratio=None, pb_ratio=None, dividend_yield=None, eps_chf=None
        )
        if self._swiss_market_data is None:
            score = self._scorer.score(ticker, _empty)
        else:
            try:
                fundamentals = await self._swiss_market_data.get_fundamentals(ticker)
                score = self._scorer.score(ticker, fundamentals)
            except Exception:
                score = self._scorer.score(ticker, _empty)
        return score.composite, today

    async def _check_eligible(self, ticker: str) -> bool:
        if self._swiss_stock_repo is None:
            return False
        stock = await self._swiss_stock_repo.get_by_ticker(ticker)
        if stock is None:
            return False
        return self._eligibility.check(stock).eligible
