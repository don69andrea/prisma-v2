"""Pydantic-Schemas für Crypto Signal Engine REST-Endpunkte.

Definiert:
  SignalVector — Ausgang des SignalService.evaluate() pro Coin
  BacktestReport — Ausgang des Walk-Forward-Backtests pro Coin
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

__all__ = ["SignalVector", "BacktestReport", "MetaLabelReport"]


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


class MetaLabelReport(BaseModel):
    """Meta-Labeling-Bericht: always-trade vs. meta-gefilterter Strategie-Vergleich.

    finding-Logik:
    - "positive": meta_filtered_sharpe > always_trade_sharpe UND
                  meta_filtered_calmar > always_trade_calmar
    - "secondary_pass": n_trades_filtered < n_trades_always * 0.9 UND
                        meta_filtered_sharpe >= always_trade_sharpe * 0.95
    - "negative": keine der obigen Bedingungen erfüllt
    """

    coin: str
    label_method: Literal["triple_barrier", "trend_scan"]
    classifier: Literal["logreg", "lgbm"]
    n_folds: int
    oos_precision: float
    oos_recall: float
    always_trade_sharpe: float
    always_trade_calmar: float
    meta_filtered_sharpe: float
    meta_filtered_calmar: float
    n_trades_always: int
    n_trades_filtered: int
    beats_baseline: bool
    finding: Literal["positive", "secondary_pass", "negative"]
    finding_reason: str
