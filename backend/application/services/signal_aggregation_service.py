"""Signal Aggregation Service — BUY/HOLD/WATCH aus Quant + ML + Macro."""

from __future__ import annotations

import logging

from backend.application.services.ml_feature_service import MLFeatureService
from backend.application.services.ml_prediction_service import MLPredictionService
from backend.domain.value_objects.decision_signal import DecisionSignal

_logger = logging.getLogger(__name__)

# Gewichtung: Quant 45%, ML 35%, Macro 20%
_W_QUANT = 0.45
_W_ML = 0.35
_W_MACRO = 0.20

# ML-Signal → numerischer Score (0–100)
_ML_SIGNAL_TO_SCORE: dict[str, float] = {
    "OUTPERFORM": 85.0,
    "NEUTRAL": 50.0,
    "UNDERPERFORM": 15.0,
}

# 3a-eligible Swiss tickers (FINMA/BVV2 Large-Cap SPI)
_3A_ELIGIBLE = frozenset(
    {
        "NESN",
        "NOVN",
        "ROG",
        "UBSG",
        "ABBN",
        "CSGN",
        "SREN",
        "SCMN",
        "SLHN",
        "BALN",
        "GEBN",
        "ZURN",
        "ALC",
        "GIVN",
        "LOGN",
        "LONN",
        "PGHN",
        "SIKA",
        "STMN",
        "TEMN",
    }
)


def _snb_macro_score(snb_rate: float) -> float:
    """Konvertiert SNB-Leitzins zu Macro-Score (0–100).

    Niedrigerer Zins = akkommodative Geldpolitik = positiver für Aktien.
    """
    if snb_rate <= 0.0:
        return 80.0
    if snb_rate <= 0.5:
        return 65.0
    if snb_rate <= 1.0:
        return 50.0
    if snb_rate <= 1.5:
        return 35.0
    return 20.0


def _is_3a_eligible(ticker: str) -> bool:
    return ticker.upper() in _3A_ELIGIBLE


class SignalAggregationService:
    """Aggregiert Quant-, ML- und Macro-Signale zu einem BUY/HOLD/WATCH-Signal."""

    def __init__(
        self,
        feature_service: MLFeatureService | None = None,
        prediction_service: MLPredictionService | None = None,
    ) -> None:
        self._feature_service = feature_service or MLFeatureService()
        self._prediction_service = prediction_service or MLPredictionService(
            feature_service=self._feature_service
        )

    async def get_signal(self, ticker: str) -> DecisionSignal | None:
        """Berechnet das aggregierte Signal für einen Ticker."""
        features = await self._feature_service.build_features(ticker)
        if features is None:
            _logger.warning("Keine Features für %s — Signal wird übersprungen", ticker)
            return None

        quant_score = features.quant_score

        # ML-Score: Versuch ML-Prediction; bei fehlendem Modell → Fallback auf Neutral
        ml_score = 50.0
        try:
            prediction = await self._prediction_service.predict(ticker)
            if prediction is not None:
                ml_score = _ML_SIGNAL_TO_SCORE.get(prediction.signal, 50.0)
        except FileNotFoundError:
            _logger.info("Kein ML-Modell vorhanden — Fallback auf NEUTRAL für %s", ticker)
        except Exception:
            _logger.exception("ML-Prediction fehlgeschlagen für %s — Fallback NEUTRAL", ticker)

        macro_score = _snb_macro_score(features.snb_rate)
        weighted_score = _W_QUANT * quant_score + _W_ML * ml_score + _W_MACRO * macro_score
        signal = DecisionSignal.signal_for_score(weighted_score)
        confidence = round(weighted_score / 100.0, 4)

        return DecisionSignal(
            ticker=ticker.upper(),
            snapshot_date=features.snapshot_date,
            signal=signal,
            confidence=confidence,
            weighted_score=round(weighted_score, 2),
            quant_score=round(quant_score, 2),
            ml_score=round(ml_score, 2),
            macro_score=round(macro_score, 2),
            is_3a_eligible=_is_3a_eligible(ticker),
        )

    async def get_signals(self, tickers: list[str]) -> list[DecisionSignal]:
        """Berechnet Signale für eine Liste von Tickern (fehlgeschlagene werden übersprungen)."""
        results: list[DecisionSignal] = []
        for ticker in tickers:
            try:
                signal = await self.get_signal(ticker)
                if signal is not None:
                    results.append(signal)
            except Exception:
                _logger.exception("Signal-Berechnung fehlgeschlagen für %s", ticker)
        return results
