"""Portfolio-Rebalancing-Service — berechnet Rebalancing-Plan ohne Persistenz."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.value_objects.rebalancing_plan import RebalancingPlan, RebalancingStep

_logger = logging.getLogger(__name__)

# Standardkosten pro Trade (z.B. 0.1% = 0.001)
_DEFAULT_TRANSACTION_COST_RATE = 0.001

# Minimale absolute Gewichtsdifferenz, ab der eine Transaktion ausgelöst wird
_MIN_DELTA_THRESHOLD = 0.005


class UnknownTickersError(ValueError):
    """Wird ausgelöst, wenn current_weights/target_weights unbekannte Ticker enthalten.

    W-9 / F-PORT-4: Frei erfundene Ticker (z.B. "FAKE0") dürfen nicht klaglos
    mit HTTP 200 verarbeitet werden — sie müssen gegen das bekannte
    Aktien-Universum (SwissStockRepository) validiert werden.
    """

    def __init__(self, tickers: list[str]) -> None:
        self.tickers = tickers
        super().__init__(f"Unbekannte Ticker: {', '.join(tickers)}")


class RebalancingService:
    """Berechnet Rebalancing-Schritte aus Ist- und Soll-Allokation.

    Parameters
    ----------
    stock_repo:
        Optional. Wird benötigt, um 3a-Eignung zu prüfen (is_3a_account=True).
        Falls None, gilt jede Position als nicht 3a-geprüft (is_3a_eligible=False).
    transaction_cost_rate:
        Transaktionskostensatz pro Trade (default: 0.1 %).
    """

    def __init__(
        self,
        stock_repo: Any | None = None,
        transaction_cost_rate: float = _DEFAULT_TRANSACTION_COST_RATE,
    ) -> None:
        self._stock_repo = stock_repo
        self._transaction_cost_rate = transaction_cost_rate
        self._eligibility_filter = EligibilityFilter()

    async def compute_plan(
        self,
        total_portfolio_value_chf: float,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        is_3a_account: bool = False,
    ) -> RebalancingPlan:
        """Berechnet einen Rebalancing-Plan.

        Parameters
        ----------
        total_portfolio_value_chf:
            Gesamtportfoliowert in CHF.
        current_weights:
            Ist-Gewichtung je Ticker (z.B. {"NESN": 0.30, "NOVN": 0.20}).
            Summe sollte ~1.0 ergeben (wird aber nicht erzwungen).
        target_weights:
            Soll-Gewichtung je Ticker. Nur Ticker mit Zielgewicht werden
            im Plan berücksichtigt.
        is_3a_account:
            Wenn True, werden nicht 3a-geeignete Positionen markiert.
        """
        total_current = sum(current_weights.values())
        total_target = sum(target_weights.values())
        if abs(total_current - 1.0) > 0.05:
            _logger.warning("Ist-Gewichte summieren zu %.3f statt 1.0", total_current)
        if abs(total_target - 1.0) > 0.05:
            _logger.warning("Soll-Gewichte summieren zu %.3f statt 1.0", total_target)
        for ticker, w in current_weights.items():
            if w < 0:
                _logger.warning("Leerverkauf erkannt: %s mit Gewicht %.3f", ticker, w)

        all_tickers = set(current_weights) | set(target_weights)
        await self._validate_known_tickers(all_tickers)
        eligibility_map = await self._resolve_eligibility(all_tickers, is_3a_account)

        steps: list[RebalancingStep] = []
        for ticker in sorted(all_tickers):
            current_w = current_weights.get(ticker, 0.0)
            target_w = target_weights.get(ticker, 0.0)
            delta = target_w - current_w

            action: Literal["BUY", "SELL", "HOLD"]
            if abs(delta) < _MIN_DELTA_THRESHOLD:
                action = "HOLD"
            elif delta > 0:
                action = "BUY"
            else:
                action = "SELL"

            estimated_value = abs(delta) * total_portfolio_value_chf
            cost = estimated_value * self._transaction_cost_rate if action != "HOLD" else 0.0

            steps.append(
                RebalancingStep(
                    ticker=ticker,
                    action=action,
                    current_weight=current_w,
                    target_weight=target_w,
                    delta_weight=delta,
                    estimated_value_chf=estimated_value,
                    transaction_cost_chf=cost,
                    is_3a_eligible=eligibility_map.get(ticker, False),
                )
            )

        total_cost = sum(s.transaction_cost_chf for s in steps)
        return RebalancingPlan(
            plan_id=uuid.uuid4(),
            steps=tuple(steps),
            total_portfolio_value_chf=total_portfolio_value_chf,
            total_transaction_cost_chf=total_cost,
            is_3a_account=is_3a_account,
            computed_at=datetime.now(tz=UTC),
        )

    async def _validate_known_tickers(self, tickers: set[str]) -> None:
        """Prüft alle Ticker gegen das bekannte Aktien-Universum.

        Ohne injiziertes Repository kann nicht validiert werden — bestehendes
        Verhalten bleibt erhalten (kein Crash für ältere Aufrufer).
        """
        if self._stock_repo is None:
            return

        unknown: list[str] = []
        for ticker in sorted(tickers):
            try:
                stock: SwissStock | None = await self._stock_repo.get_by_ticker(ticker)
            except Exception:
                stock = None
            if stock is None:
                unknown.append(ticker)

        if unknown:
            raise UnknownTickersError(unknown)

    async def _resolve_eligibility(self, tickers: set[str], is_3a_account: bool) -> dict[str, bool]:
        if not is_3a_account:
            # No 3a restriction for non-3a accounts — all stocks are eligible.
            return {ticker: True for ticker in tickers}
        if self._stock_repo is None:
            return {ticker: False for ticker in tickers}

        result: dict[str, bool] = {}
        for ticker in tickers:
            try:
                stock: SwissStock | None = await self._stock_repo.get_by_ticker(ticker)
                if stock is None:
                    result[ticker] = False
                else:
                    er = self._eligibility_filter.check(stock)
                    result[ticker] = er.eligible
            except Exception:
                result[ticker] = False
        return result
