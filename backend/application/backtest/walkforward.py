"""Expanding-Window Walk-Forward Backtest Engine (A7.6, A7.7).

Kernlogik:
- Expanding Window: min_train Handelstage als erstes Trainingsfenster
- Exposure-Matched Baseline: Buy-and-Hold mit Ø-Exposure der Strategie
- Netto-Kosten: 0.1% pro Handelsvolumen-Einheit (Turnover × 0.001)
- beats_exposure_matched: True nur wenn BEIDE Sharpe UND Calmar > Baseline

PoC-Reproduktion (A7.3):
  BTC: Strategie Calmar 1.31 vs Baseline 0.60 (Trend-Following + Vol-Targeting)
  Das Muster (Signal > Baseline) muss auf trendigem Datensatz reproduzierbar sein.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.interfaces.rest.schemas.signals import BacktestReport

__all__ = ["run_walkforward", "run_walkforward_with_details"]

# Annualisierungsfaktor: Krypto handelt 365 Tage, Aktien 252
_ANN = 252


# ---------------------------------------------------------------------------
# Hilfsfunktionen (Quant-Metriken)
# ---------------------------------------------------------------------------


def _sharpe(returns: pd.Series, ann: int = _ANN) -> float:
    """Annualisierter Sharpe Ratio. 0 bei fehlender Varianz."""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    return float(np.sqrt(ann) * returns.mean() / returns.std())


def _cagr(returns: pd.Series, ann: int = _ANN) -> float:
    """Compound Annual Growth Rate."""
    if len(returns) == 0:
        return 0.0
    total = float((1 + returns).prod())
    if total <= 0:
        return -1.0
    return float(total ** (ann / len(returns)) - 1)


def _max_drawdown(returns: pd.Series) -> float:
    """Maximum Drawdown (negativ, z. B. -0.25 = -25%)."""
    if len(returns) == 0:
        return 0.0
    equity = (1 + returns).cumprod()
    running_max = equity.cummax()
    dd = equity / running_max - 1
    return float(dd.min())


def _calmar(returns: pd.Series, ann: int = _ANN) -> float:
    """Calmar Ratio = CAGR / |MaxDD|. 0 wenn kein Drawdown."""
    dd = _max_drawdown(returns)
    c = _cagr(returns, ann)
    if dd == 0:
        return 0.0
    return float(c / abs(dd))


def _equity_curve(returns: pd.Series) -> list[tuple[date, float]]:
    """Equity-Kurve als Liste von (date, equity_value)-Tupeln. Startet bei 1.0."""
    equity = (1 + returns).cumprod()
    # Sicherstellen, dass Equity nie negativ ist (Long-Only-Garantie)
    equity = equity.clip(lower=0.0)
    result: list[tuple[date, float]] = []
    for idx, val in equity.items():
        dt = idx.date() if hasattr(idx, "date") else idx
        result.append((dt, float(val)))
    return result


# ---------------------------------------------------------------------------
# Kernfunktion: run_walkforward
# ---------------------------------------------------------------------------


def run_walkforward(
    prices: pd.DataFrame,
    signals: pd.Series,
    coin: str = "UNKNOWN",
    costs: float = 0.001,
    min_train: int = 252,
    step: int = 63,
    meta_filter: pd.Series | None = None,
) -> BacktestReport:
    """Führt einen expanding-window Walk-Forward-Backtest durch.

    Args:
        prices: DataFrame mit mindestens einer 'close'-Spalte; DatetimeIndex.
        signals: Series[0/1] (1 = investiert, 0 = Cash), am selben Index wie prices.
                 Die Engine wendet intern shift(1) an, um Look-Ahead zu verhindern.
        coin: Bezeichnung des Instruments für den BacktestReport.
        costs: Transaktionskosten pro Handels-Einheit (default: 0.001 = 0.1%).
        min_train: Mindestanzahl Trainingstage (default: 252).
        step: Schrittweite in Tagen für das Expanding Window (default: 63).
        meta_filter: Optionale Series {0, 1} — 1 = Trade erlaubt, 0 = Position maskiert.
                     Default None = kein Filter (identisches Verhalten wie bisher, ML-08).

    Returns:
        BacktestReport (Pydantic) mit allen Metriken.
    """
    details = run_walkforward_with_details(
        prices=prices,
        signals=signals,
        costs=costs,
        min_train=min_train,
        step=step,
        meta_filter=meta_filter,
    )

    return BacktestReport(
        coin=coin,
        cagr=details["strategy_cagr"],
        sharpe=details["strategy_sharpe"],
        max_dd=details["strategy_max_dd"],
        calmar=details["strategy_calmar"],
        beats_exposure_matched=details["beats_exposure_matched"],
        n_trades=details["n_trades"],
        equity_curve=_equity_curve(details["net_returns"]),
    )


def run_walkforward_with_details(
    prices: pd.DataFrame,
    signals: pd.Series,
    costs: float = 0.001,
    min_train: int = 252,
    step: int = 63,
    meta_filter: pd.Series | None = None,
) -> dict[str, Any]:
    """Wie run_walkforward, gibt aber alle Zwischengrößen zurück (für Tests).

    Zusätzliche Schlüssel im Rückgabe-Dict:
        net_returns, gross_returns, baseline_returns, trade_mask,
        avg_exposure, n_trades,
        strategy_sharpe, strategy_calmar, strategy_cagr, strategy_max_dd,
        baseline_sharpe, baseline_calmar,
        beats_exposure_matched.
    """
    # -----------------------------------------------------------------------
    # 1. Daten ausrichten und bereinigen
    # -----------------------------------------------------------------------
    close = prices["close"].copy()

    # Signals auf den gleichen Index ausrichten
    signals = signals.reindex(close.index).fillna(0.0)

    # Tagesrenditen
    daily_ret = close.pct_change()

    # -----------------------------------------------------------------------
    # 2. Signal shift(1): Verhindert Look-Ahead (Feature an t verwendet close@t-1)
    # -----------------------------------------------------------------------
    # Das Signal an Tag t sagt, ob wir MORGEN (t+1) investiert sein wollen.
    # shift(1) stellt sicher, dass die Entscheidung nur auf Vergangenheitsdaten basiert.
    position = signals.shift(1).fillna(0.0).clip(0.0, 1.5)

    # -----------------------------------------------------------------------
    # 2b. Meta-Filter Masking (ML-07, ML-08)
    # -----------------------------------------------------------------------
    # Wenn meta_filter gesetzt ist, werden Positionen auf 0 maskiert wo filter=0.
    # Default None → kein Masking (backward-kompatibel, ML-08).
    if meta_filter is not None:
        meta_aligned = meta_filter.reindex(close.index).fillna(0.0)
        position = position * meta_aligned

    # -----------------------------------------------------------------------
    # 3. Brutto-Rendite der Strategie (vor Kosten)
    # -----------------------------------------------------------------------
    gross_returns = daily_ret * position

    # -----------------------------------------------------------------------
    # 4. Turnover und Netto-Kosten (A7.7)
    # -----------------------------------------------------------------------
    turnover = position.diff().abs().fillna(0.0)
    cost_series = turnover * costs
    net_returns = gross_returns - cost_series

    # Trade-Maske: Tage, an denen sich die Position ändert
    trade_mask = turnover > 0.0

    n_trades = int(trade_mask.sum())

    # -----------------------------------------------------------------------
    # 5. Exposure-Matched Baseline (A7.6)
    # -----------------------------------------------------------------------
    # Ø-Exposure der Strategie (über den gesamten Testzeitraum)
    avg_exposure = float(position.mean())

    # Baseline: konstante Investitionsquote = Ø-Exposure, kein Timing
    # Kein Turnover → nahezu keine Kosten (einmaliger Kauf am Anfang)
    baseline_returns = daily_ret * avg_exposure

    # -----------------------------------------------------------------------
    # 6. Metriken berechnen (NaN-Zeile am Anfang entfernen)
    # -----------------------------------------------------------------------
    net_clean = net_returns.dropna()
    gross_clean = gross_returns.dropna()
    baseline_clean = baseline_returns.dropna()

    strat_sharpe = _sharpe(net_clean)
    strat_calmar = _calmar(net_clean)
    strat_cagr = _cagr(net_clean)
    strat_max_dd = _max_drawdown(net_clean)

    base_sharpe = _sharpe(baseline_clean)
    base_calmar = _calmar(baseline_clean)

    # -----------------------------------------------------------------------
    # 7. beats_exposure_matched: BEIDE Sharpe UND Calmar müssen besser sein
    # -----------------------------------------------------------------------
    beats = bool(strat_sharpe > base_sharpe and strat_calmar > base_calmar)

    return {
        "net_returns": net_clean,
        "gross_returns": gross_clean,
        "baseline_returns": baseline_clean,
        "trade_mask": trade_mask.loc[net_clean.index],
        "avg_exposure": avg_exposure,
        "n_trades": n_trades,
        "strategy_sharpe": strat_sharpe,
        "strategy_calmar": strat_calmar,
        "strategy_cagr": strat_cagr,
        "strategy_max_dd": strat_max_dd,
        "baseline_sharpe": base_sharpe,
        "baseline_calmar": base_calmar,
        "beats_exposure_matched": beats,
    }
