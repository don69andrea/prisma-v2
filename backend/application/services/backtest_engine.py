"""BacktestEngine — Contract E3 / TEIL C §C6.

Event-getriebene, day-by-day Simulation. KEIN Look-Ahead.
Live-Outcomes und historischer Backtest nutzen diese EINE Engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from backend.domain.services.transaction_cost_model import AssetClass, TransactionCostModel


@dataclass(frozen=True)
class SignalEvent:
    ticker: str
    date: date
    signal: str           # "BUY" | "SELL"
    price: float
    asset_class: AssetClass
    horizon_days: int = 30
    weighted_score: float = 0.0


@dataclass(frozen=True)
class Fill:
    ticker: str
    date: date
    side: str             # "ENTRY" | "EXIT"
    price: float
    cost: float           # als Bruchteil des Preises


@dataclass
class EquityCurve:
    dates: list[date]
    equity: list[float]   # normiert auf 1.0 zum Start
    cagr: float
    sharpe: float
    max_drawdown: float
    net_alpha_vs_benchmark: float
    fills: list[Fill] = field(default_factory=list)


def _next_trading_day(prices: pd.DataFrame, from_date: date, n: int) -> date | None:
    """Gibt den n-ten Handelstag nach from_date zurück (nur Tage im Index)."""
    idx = prices.index
    mask = idx > pd.Timestamp(from_date)
    future = idx[mask]
    if len(future) < n:
        return None
    return future[n - 1].date()


def _sharpe(returns: np.ndarray, periods_per_year: float = 12.0) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(np.std(returns, ddof=1))
    if std < 1e-9:
        return 0.0
    return float(np.mean(returns) / std * math.sqrt(periods_per_year))


def _cagr(equity: list[float], n_years: float) -> float:
    if n_years <= 0 or equity[0] <= 0:
        return 0.0
    return float((equity[-1] / equity[0]) ** (1.0 / n_years) - 1.0)


def _max_drawdown(equity: list[float]) -> float:
    arr = np.array(equity, dtype=float)
    peak = np.maximum.accumulate(arr)
    with np.errstate(invalid="ignore"):
        dd = (arr - peak) / np.where(peak > 0, peak, np.nan)
    return float(np.nanmin(dd)) if len(dd) > 0 else 0.0


class BacktestEngine:
    """Single-source-of-truth für historischen Backtest UND Live-Signal-Outcomes.

    Algorithmus (event-getrieben, kein Look-Ahead):
    - Für jedes BUY-Signal: Position läuft für horizon_days Handelstage.
    - An Tag d wird nur data[data.index <= d] verwendet.
    - Fills enthalten TC aus TransactionCostModel.
    - outcomes_from() erzeugt signal_outcomes-Zeilen (netto).
    """

    def __init__(
        self,
        cost_model: TransactionCostModel,
        benchmark_ticker: str,
    ) -> None:
        self._cost = cost_model
        self._benchmark = benchmark_ticker

    async def run(
        self,
        signals: list[SignalEvent],
        prices: pd.DataFrame,
        benchmark: pd.Series,
        start: date,
        end: date,
    ) -> EquityCurve:
        """Simuliert Portfolio-Performance über [start, end].

        prices: DataFrame mit Tickern als Spalten, DatetimeIndex.
        benchmark: Series mit DatetimeIndex (Benchmark-Preise).
        KEIN Look-Ahead: Signale auf Tag d nutzen nur Preise ≤ d.
        """
        prices = prices.loc[
            (prices.index >= pd.Timestamp(start)) & (prices.index <= pd.Timestamp(end))
        ].copy()
        benchmark = benchmark.loc[
            (benchmark.index >= pd.Timestamp(start)) & (benchmark.index <= pd.Timestamp(end))
        ].copy()

        if prices.empty:
            return EquityCurve([], [], 0.0, 0.0, 0.0, 0.0)

        # Positions: ticker -> list of (entry_date, entry_price, exit_date, asset_class)
        buys_only = [s for s in signals if s.signal == "BUY"]
        buy_map: dict[date, list[SignalEvent]] = {}
        for sig in buys_only:
            buy_map.setdefault(sig.date, []).append(sig)

        # Bilde pro Signal ein Exit-Datum
        position_returns: list[float] = []   # netto, pro abgeschlossener Position
        all_fills: list[Fill] = []

        for sig in buys_only:
            exit_date = _next_trading_day(prices, sig.date, sig.horizon_days)
            if exit_date is None:
                continue
            if sig.ticker not in prices.columns:
                continue

            ts_entry = pd.Timestamp(sig.date)
            ts_exit = pd.Timestamp(exit_date)
            price_col = prices[sig.ticker]

            # Einstiegspreis: schliess-Preis am Signal-Datum (≤ d → kein Look-Ahead)
            if ts_entry not in price_col.index:
                continue
            p_entry = float(price_col.loc[ts_entry])
            if ts_exit not in price_col.index:
                continue
            p_exit = float(price_col.loc[ts_exit])

            if p_entry <= 0 or p_exit <= 0:
                continue

            gross = (p_exit - p_entry) / p_entry
            rt_cost = self._cost.round_trip_cost(sig.asset_class)
            net = gross - rt_cost

            position_returns.append(net)
            all_fills.append(Fill(sig.ticker, sig.date, "ENTRY", p_entry, rt_cost / 2))
            all_fills.append(Fill(sig.ticker, exit_date, "EXIT", p_exit, rt_cost / 2))

        # Equity-Kurve: monatliche Aggregation der gleichgewichteten Positions
        equity_dates, equity_values = self._build_equity_curve(
            buys_only, prices, position_returns
        )

        # Benchmark-Equity
        bm_returns = benchmark.pct_change().dropna()
        bm_equity = (1.0 + bm_returns).cumprod()
        if len(bm_equity) > 0:
            bm_total = float(bm_equity.iloc[-1] - 1.0)
        else:
            bm_total = 0.0

        n_years = len(equity_dates) / 12.0 if equity_dates else 0.0
        cagr = _cagr(equity_values, n_years)
        bm_cagr = _cagr(list(bm_equity.values), len(bm_equity) / 252.0) if len(bm_equity) > 1 else 0.0

        monthly_rets = np.diff(np.log(np.maximum(equity_values, 1e-9))) if len(equity_values) > 1 else np.array([])
        sh = _sharpe(monthly_rets, 12.0)
        mdd = _max_drawdown(equity_values)
        alpha = cagr - bm_cagr

        return EquityCurve(
            dates=equity_dates,
            equity=equity_values,
            cagr=round(cagr, 6),
            sharpe=round(sh, 4),
            max_drawdown=round(mdd, 6),
            net_alpha_vs_benchmark=round(alpha, 6),
            fills=all_fills,
        )

    def _build_equity_curve(
        self,
        signals: list[SignalEvent],
        prices: pd.DataFrame,
        position_returns: list[float],
    ) -> tuple[list[date], list[float]]:
        """Monatliche Equity-Kurve aus abgeschlossenen Positions."""
        if not position_returns:
            return [], [1.0]

        # Gruppiere Signale nach Monat (YYYY-MM)
        monthly: dict[str, list[float]] = {}
        ret_idx = 0
        for sig in signals:
            exit_date = _next_trading_day(prices, sig.date, sig.horizon_days)
            if exit_date is None or sig.ticker not in prices.columns:
                continue
            ts_entry = pd.Timestamp(sig.date)
            ts_exit = pd.Timestamp(exit_date)
            if ts_entry not in prices[sig.ticker].index or ts_exit not in prices[sig.ticker].index:
                continue
            key = sig.date.strftime("%Y-%m")
            if ret_idx < len(position_returns):
                monthly.setdefault(key, []).append(position_returns[ret_idx])
                ret_idx += 1

        if not monthly:
            return [], [1.0]

        months_sorted = sorted(monthly.keys())
        eq = 1.0
        dates: list[date] = []
        values: list[float] = [1.0]

        for m in months_sorted:
            rets = monthly[m]
            avg_ret = float(np.mean(rets))
            eq *= (1.0 + avg_ret)
            y, mo = int(m[:4]), int(m[5:])
            last_day_of_month = date(y, mo, 28)  # annäherungsweise
            dates.append(last_day_of_month)
            values.append(round(eq, 6))

        return dates, values

    async def outcomes_from(
        self,
        signals: list[SignalEvent],
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> list[dict[str, Any]]:
        """Erzeugt signal_outcomes-Zeilen (netto: cost_adjusted_return, net_excess_return).

        Dieselbe Return-Logik wie run() → keine zweite Wahrheit (E3.2).
        """
        rows: list[dict[str, Any]] = []
        import uuid

        for sig in signals:
            if sig.signal != "BUY":
                continue
            if sig.ticker not in prices.columns:
                continue

            exit_date = _next_trading_day(prices, sig.date, sig.horizon_days)
            if exit_date is None:
                continue

            ts_entry = pd.Timestamp(sig.date)
            ts_exit = pd.Timestamp(exit_date)
            price_col = prices[sig.ticker]

            if ts_entry not in price_col.index or ts_exit not in price_col.index:
                continue

            p_entry = float(price_col.loc[ts_entry])
            p_exit = float(price_col.loc[ts_exit])
            if p_entry <= 0 or p_exit <= 0:
                continue

            gross = (p_exit - p_entry) / p_entry
            rt_cost = self._cost.round_trip_cost(sig.asset_class)
            cost_adj = gross - rt_cost

            # Benchmark-Return über denselben Zeitraum
            bm_slice = benchmark.loc[ts_entry:ts_exit]
            bm_return = None
            net_excess = None
            if len(bm_slice) >= 2:
                bm_return = float((bm_slice.iloc[-1] / bm_slice.iloc[0]) - 1.0)
                net_excess = cost_adj - bm_return

            was_correct = cost_adj > 0 if net_excess is None else cost_adj > 0

            asset_type = "stock" if sig.asset_class == AssetClass.CH_STOCK else "crypto"

            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "ticker": sig.ticker,
                    "asset_type": asset_type,
                    "signal_date": sig.date,
                    "signal": sig.signal,
                    "price_at_signal": p_entry,
                    "horizon_days": sig.horizon_days,
                    "evaluation_date": exit_date,
                    "price_at_eval": p_exit,
                    "actual_return": round(gross, 6),
                    "benchmark_ret": round(bm_return, 6) if bm_return is not None else None,
                    "excess_return": round(gross - (bm_return or 0.0), 6),
                    "cost_adjusted_return": round(cost_adj, 6),
                    "net_excess_return": round(net_excess, 6) if net_excess is not None else None,
                    "was_correct": was_correct,
                    "used_for_train": False,
                    "source_table": f"{asset_type}_daily_signals",
                }
            )

        return rows
