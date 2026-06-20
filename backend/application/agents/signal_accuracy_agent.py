"""SignalAccuracyAgent — Kap. 5.1 / TEIL G Phase 3.

Befüllt und evaluiert signal_outcomes via BacktestEngine (EINE Engine, kein zweiter Return-Pfad).
Berechnet Net-Win-Rate / Alpha nach Kosten.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from backend.application.services.backtest_engine import BacktestEngine, SignalEvent
from backend.domain.services.transaction_cost_model import TransactionCostModel
from backend.infrastructure.persistence.repositories.signal_outcome_repository import (
    SignalOutcomeRepository,
)

_logger = logging.getLogger(__name__)

# Minimale Win-Rate (netto) um den Edge als validiert zu bezeichnen
MIN_WIN_RATE_NET: float = 0.48


class SignalAccuracyAgent:
    """Befüllt signal_outcomes und berechnet Win-Rate/Alpha (netto).

    Nutzt die BacktestEngine als Single-Source für Return-Berechnung.
    Unterstützt beide Asset-Klassen: CH-Aktien + Krypto.
    """

    def __init__(
        self,
        outcome_repo: SignalOutcomeRepository,
        backtest_engine: BacktestEngine | None = None,
        cost_model: TransactionCostModel | None = None,
    ) -> None:
        self._repo = outcome_repo
        self._cost = cost_model or TransactionCostModel()
        self._engine = backtest_engine or BacktestEngine(
            cost_model=self._cost,
            benchmark_ticker="^SSMI",
        )

    async def populate_outcomes(
        self,
        signals: list[SignalEvent],
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> int:
        """Berechnet und speichert Outcomes für gegebene Signale.

        Idempotent: existierende Outcomes werden per UPSERT überschrieben.
        Gibt Anzahl gespeicherter Rows zurück.
        """
        rows = await self._engine.outcomes_from(signals, prices, benchmark)
        return await self._repo.bulk_upsert(rows)

    async def evaluate(
        self,
        *,
        asset_type: str | None = None,
        since: date | None = None,
    ) -> dict[str, Any]:
        """Berechnet Win-Rate / Avg-Return / Alpha für gespeicherte Outcomes.

        Gibt ausschliesslich NETTO-Metriken zurück (cost_adjusted_return).
        """
        stats = await self._repo.win_rate(asset_type=asset_type, since=since)

        edge_verdict = "KEIN EDGE" if stats["win_rate"] < MIN_WIN_RATE_NET else "EDGE VORHANDEN"
        if stats["n"] < 30:
            edge_verdict = f"ZU WENIG DATEN (n={stats['n']}, min=30)"

        return {
            **stats,
            "min_win_rate_threshold": MIN_WIN_RATE_NET,
            "edge_verdict": edge_verdict,
        }

    async def run_full_evaluation(
        self,
        signals: list[SignalEvent],
        prices: pd.DataFrame,
        benchmark: pd.Series,
        *,
        asset_type: str | None = None,
        since: date | None = None,
    ) -> dict[str, Any]:
        """Populate + Evaluate in einem Schritt.

        Typischer Aufruf im SignalAccuracy-Cron.
        """
        n_saved = await self.populate_outcomes(signals, prices, benchmark)
        _logger.info("SignalAccuracyAgent: %d Outcomes gespeichert", n_saved)

        result = await self.evaluate(asset_type=asset_type, since=since)
        _logger.info(
            "SignalAccuracyAgent: Win-Rate=%.1f%% n=%d → %s",
            result["win_rate"] * 100,
            result["n"],
            result["edge_verdict"],
        )
        return result
