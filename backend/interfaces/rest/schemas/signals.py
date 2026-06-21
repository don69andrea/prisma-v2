"""Pydantic-Schemas für Crypto Signal Engine REST-Endpunkte.

Definiert:
  SignalVector — Ausgang des SignalService.evaluate() pro Coin
  BacktestReport — Ausgang des Walk-Forward-Backtests pro Coin
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

__all__ = ["SignalVector", "BacktestReport"]


class SignalVector(BaseModel):
    """Vollständiger Signal-Vektor für einen Coin zu einem Stichtag.

    Aggregiert Layers 1-3 der Signal Engine:
    - Layer 1: Cross-Sectional Momentum + On-Chain Health
    - Layer 2: 2-of-3 Indicator Consensus (MA, MACD, RSI)
    - Layer 3: Vol-Targeting Sizing + Drawdown-Brake

    Hinweis: SELL bedeutet immer Exposure = 0 (kein Short, kein negativer Faktor).
    """

    coin: str
    asof: date
    action: Literal["BUY", "HOLD", "SELL"]
    size_factor: float = Field(ge=0.0, le=1.5)
    consensus: str  # z. B. "2/3", "3/3"
    sub_scores: dict[
        str, float
    ]  # ma_signal, macd_signal, rsi_signal, vol_pred, momentum_rank, onchain_score
    confidence: float = Field(ge=0.0, le=1.0)
    disclaimer: str = "Entscheidungsunterstützung, kein Anlagerat."


class BacktestReport(BaseModel):
    """Walk-Forward-Backtest-Bericht für einen Coin.

    beats_exposure_matched: True wenn Signal-Strategie Sharpe UND Calmar
    der Exposure-Matched-Baseline übertrifft (netto nach 0.1% Transaktionskosten).
    """

    coin: str
    cagr: float
    sharpe: float
    max_dd: float
    calmar: float
    beats_exposure_matched: bool
    n_trades: int
    equity_curve: list[tuple[date, float]]
