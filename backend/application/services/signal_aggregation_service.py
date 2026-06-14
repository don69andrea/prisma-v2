"""Signal Aggregation Service — BUY/HOLD/WATCH aus Quant + ML + Macro."""

from __future__ import annotations

import logging

from backend.application.agents.macro_agent import MacroIntelligenceAgent
from backend.application.services.ml_feature_service import MLFeatureService
from backend.application.services.ml_prediction_service import MLPredictionService
from backend.config import get_settings
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.value_objects.decision_signal import DecisionSignal

_logger = logging.getLogger(__name__)

# Max. parallele Signal-Berechnungen — jede lädt yfinance-DataFrame + optionaler LLM-Call.
# Render Free-Tier: 512 MB RAM. 4 × ~80 MB Peak = ~320 MB → sicherer Puffer.
_MAX_CONCURRENT_SIGNALS = 4

# ML-Signal → numerischer Score (0–100)
_ML_SIGNAL_TO_SCORE: dict[str, float] = {
    "OUTPERFORM": 85.0,
    "NEUTRAL": 50.0,
    "UNDERPERFORM": 15.0,
}


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


class SignalAggregationService:
    """Aggregiert Quant-, ML- und Macro-Signale zu einem BUY/HOLD/WATCH-Signal."""

    def __init__(
        self,
        feature_service: MLFeatureService | None = None,
        prediction_service: MLPredictionService | None = None,
        swiss_stock_repo: object | None = None,
        macro_agent: MacroIntelligenceAgent | None = None,
    ) -> None:
        self._feature_service = feature_service or MLFeatureService()
        self._prediction_service = prediction_service or MLPredictionService(
            feature_service=self._feature_service
        )
        self._swiss_stock_repo = swiss_stock_repo
        self._macro_agent = macro_agent
        self._eligibility = EligibilityFilter()
        _s = get_settings()
        self._w_quant = _s.signal_quant_weight
        self._w_ml = _s.signal_ml_weight
        self._w_macro = _s.signal_macro_weight

    async def _check_3a_eligible(self, ticker: str) -> bool:
        """Prüft 3a-Eignung via EligibilityFilter; nicht im Repo → nicht eligible."""
        if self._swiss_stock_repo is None:
            return False
        from backend.domain.repositories.swiss_stock_repository import SwissStockRepository

        repo: SwissStockRepository = self._swiss_stock_repo  # type: ignore[assignment]
        stock = await repo.get_by_ticker(ticker.upper())
        if stock is None:
            return False
        return self._eligibility.check(stock).eligible

    async def get_signal(self, ticker: str) -> DecisionSignal | None:
        """Berechnet das aggregierte Signal für einen Ticker."""
        features = await self._feature_service.build_features(ticker)
        if features is None:
            _logger.warning("Keine Features für %s — Signal wird übersprungen", ticker)
            return None

        quant_score = features.quant_score

        # ML-Score: Versuch ML-Prediction; bei fehlendem Modell → ML-Gewicht auf andere verteilen
        ml_score: float | None = None
        try:
            prediction = await self._prediction_service.predict(ticker)
            if prediction is not None:
                ml_score = _ML_SIGNAL_TO_SCORE.get(prediction.signal, 50.0)
        except FileNotFoundError:
            _logger.info("Kein ML-Modell vorhanden — ML-Gewicht wird umverteilt für %s", ticker)
        except Exception:
            _logger.exception(
                "ML-Prediction fehlgeschlagen für %s — ML-Gewicht wird umverteilt", ticker
            )

        # Per-Ticker Macro-Score wenn MacroIntelligenceAgent verfügbar, sonst global
        if self._macro_agent is not None:
            try:
                ticker_macro = await self._macro_agent.get_macro_score(ticker)
                macro_score = ticker_macro.score
            except Exception:
                _logger.warning("MacroAgent fehlgeschlagen für %s — Fallback auf SNB-Score", ticker)
                macro_score = _snb_macro_score(features.snb_rate)
        else:
            macro_score = _snb_macro_score(features.snb_rate)

        # Gewichts-Normierung: wenn ML nicht verfügbar, ML-Gewicht auf Quant + Macro verteilen
        if ml_score is not None:
            weighted_score = (
                self._w_quant * quant_score + self._w_ml * ml_score + self._w_macro * macro_score
            )
            effective_ml_score = ml_score
        else:
            available_weight = self._w_quant + self._w_macro
            w_quant_norm = self._w_quant / available_weight
            w_macro_norm = self._w_macro / available_weight
            weighted_score = w_quant_norm * quant_score + w_macro_norm * macro_score
            effective_ml_score = 50.0  # Neutral als Report-Wert
        signal = DecisionSignal.signal_for_score(weighted_score)
        confidence = round(weighted_score / 100.0, 4)
        is_eligible = await self._check_3a_eligible(ticker)

        return DecisionSignal(
            ticker=ticker.upper(),
            snapshot_date=features.snapshot_date,
            signal=signal,
            confidence=confidence,
            weighted_score=round(weighted_score, 2),
            quant_score=round(quant_score, 2),
            ml_score=round(effective_ml_score, 2),
            macro_score=round(macro_score, 2),
            is_3a_eligible=is_eligible,
        )

    async def get_signals(self, tickers: list[str]) -> list[DecisionSignal]:
        """Berechnet Signale für eine Liste von Tickern (fehlgeschlagene werden übersprungen).

        Maximal _MAX_CONCURRENT Ticker gleichzeitig — verhindert OOM durch parallele
        yfinance-DataFrames + LLM-Responses im RAM bei grossen Ticker-Listen.
        """
        import asyncio

        sem = asyncio.Semaphore(_MAX_CONCURRENT_SIGNALS)

        async def _bounded(ticker: str) -> DecisionSignal | None | BaseException:
            async with sem:
                return await self.get_signal(ticker)

        raw = await asyncio.gather(
            *[_bounded(t) for t in tickers],
            return_exceptions=True,
        )
        results: list[DecisionSignal] = []
        for ticker, outcome in zip(tickers, raw, strict=True):
            if isinstance(outcome, BaseException):
                _logger.exception(
                    "Signal-Berechnung fehlgeschlagen für %s", ticker, exc_info=outcome
                )
            elif outcome is not None:
                results.append(outcome)
        return results
