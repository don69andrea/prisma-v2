"""Portfolio Walk-Forward Backtest Engine (V4-4b).

Runs an expanding-window walk-forward backtest over the PIT (point-in-time)
crypto universe. Uses 2-of-3 indicator consensus (MA+MACD+RSI) for signals,
the portfolio allocator for weights, and the existing walkforward helpers for
metric computation.

Look-ahead guard:
- Indicator signals use prices up to date t (MA/MACD/RSI computed at t).
- Position at t = signal shifted by 1 → uses only data up to t-1.
- Rolling vol at t = rolling_30d_std shifted by 1 → uses only data up to t-1.

PIT guard:
- Coin included in portfolio only from its first_eligible_date onward.
- Equal-weight BH baseline also respects PIT eligibility per day.
"""

from __future__ import annotations

from datetime import date as _Date
from typing import Any

import numpy as np
import pandas as pd

from backend.application.backtest.portfolio import allocate_portfolio
from backend.application.backtest.universe import UniverseMembership
from backend.application.backtest.walkforward import (
    _cagr,  # type: ignore[attr-defined]
    _calmar,  # type: ignore[attr-defined]
    _equity_curve,  # type: ignore[attr-defined]
    _max_drawdown,  # type: ignore[attr-defined]
    _sharpe,  # type: ignore[attr-defined]
)
from backend.interfaces.rest.schemas.signals import (
    PortfolioBacktestReport,
    PortfolioCoinStats,
)

__all__ = ["run_portfolio_walkforward", "run_portfolio_walkforward_with_details"]

_ANN = 252
_VOL_WINDOW = 30  # rolling window for realized vol estimate
_DD_BRAKE_LEVEL: float = -0.15  # mirrors portfolio._DD_BRAKE_THRESHOLD


# ---------------------------------------------------------------------------
# Indicator helpers (inline — same logic as robustness_analysis.py)
# ---------------------------------------------------------------------------


def _ma_signal(close: pd.Series, window: int) -> pd.Series:
    ma = close.rolling(window, min_periods=window).mean()
    return (close > ma).astype(float).fillna(0.0)


def _rsi_signal(close: pd.Series, window: int = 14) -> pd.Series:
    diff = close.diff(1)
    up = diff.where(diff > 0, 0.0)
    down = (-diff).where(diff < 0, 0.0)
    avg_up = up.ewm(alpha=1 / window, adjust=False).mean()
    avg_dn = down.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_up / avg_dn.replace(0.0, np.nan)
    rsi_val = 100 - 100 / (1 + rs)
    return (rsi_val > 50).astype(float).fillna(0.0)


def _macd_signal(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return (macd_line > signal_line).astype(float).fillna(0.0)


def _consensus(close: pd.Series, ma_window: int = 100) -> pd.Series:
    """2-of-3 vote: MA + MACD + RSI. Result is NOT shifted."""
    vote = (_ma_signal(close, ma_window) + _rsi_signal(close) + _macd_signal(close)) / 3.0
    return (vote >= 0.5).astype(float)


# ---------------------------------------------------------------------------
# Core walkforward (shared by both public functions)
# ---------------------------------------------------------------------------


def _walkforward_core(
    price_data: dict[str, pd.DataFrame],
    universe: UniverseMembership,
    costs: float,
    min_train: int,
    ma_window: int,
) -> dict[str, Any]:
    """Internal walkforward — returns all data needed by both public functions.

    Keys in the returned dict:
        report                    PortfolioBacktestReport (Pydantic)
        dd_brake_dates            list[date] — OOS dates when brake fired
        per_coin_weighted_returns dict[str, pd.Series] — coin → w_i * r_i (OOS)
        bh_ew_returns             pd.Series — equal-weight BH daily returns (OOS)
        exposure_matched_returns  pd.Series — exposure-matched baseline (OOS)
        net_oos_returns           pd.Series — net portfolio daily returns (OOS)
        bh_sharpe / bh_calmar / bh_max_dd / bh_cagr  — EW-BH metrics
        em_sharpe / em_calmar / em_max_dd / em_cagr   — Exposure-matched metrics
    """
    coins = sorted(price_data.keys())

    # ── 1. Build a common aligned date index ──────────────────────────────────
    all_indices = [df.index for df in price_data.values() if not df.empty]
    if not all_indices:
        empty = _empty_report(coins, costs, universe)
        return {
            "report": empty,
            "dd_brake_dates": [],
            "per_coin_weighted_returns": {},
            "bh_ew_returns": pd.Series(dtype=float),
            "exposure_matched_returns": pd.Series(dtype=float),
            "net_oos_returns": pd.Series(dtype=float),
            "bh_sharpe": 0.0, "bh_calmar": 0.0, "bh_max_dd": 0.0, "bh_cagr": 0.0,
            "em_sharpe": 0.0, "em_calmar": 0.0, "em_max_dd": 0.0, "em_cagr": 0.0,
        }

    common_idx = all_indices[0]
    for idx in all_indices[1:]:
        common_idx = common_idx.union(idx)
    common_idx = common_idx.sort_values()

    # ── 2. Pre-compute signals and rolling vols per coin ──────────────────────
    raw_signals: dict[str, pd.Series] = {}
    daily_returns: dict[str, pd.Series] = {}
    rolling_vols: dict[str, pd.Series] = {}

    for coin in coins:
        df = price_data[coin].reindex(common_idx)
        close = df["close"].ffill()

        raw_signals[coin] = _consensus(close, ma_window).reindex(common_idx).fillna(0.0)

        ret = close.pct_change().fillna(0.0)
        daily_returns[coin] = ret

        rv = ret.rolling(_VOL_WINDOW, min_periods=_VOL_WINDOW).std() * np.sqrt(_ANN)
        rv = rv.fillna(0.3)
        rolling_vols[coin] = rv.shift(1).fillna(0.3)

    # ── 3. Build position matrix (date × coin), with shift(1) look-ahead guard
    pos_df = pd.DataFrame(
        {coin: raw_signals[coin].shift(1).fillna(0.0) for coin in coins},
        index=common_idx,
    )
    if len(common_idx) > min_train:
        pos_df.iloc[:min_train] = 0.0

    # ── 4. Build weight matrix via portfolio allocator ────────────────────────
    oos_start = min_train
    weight_df = pd.DataFrame(0.0, index=common_idx, columns=coins)

    portfolio_equity = 1.0
    running_max_equity = 1.0
    dd_brake_dates: list[_Date] = []

    for i in range(oos_start, len(common_idx)):
        t = common_idx[i]
        t_date = t.date() if hasattr(t, "date") else t

        eligible = universe.eligible_coins(t_date)
        if not eligible:
            continue

        signals_dict: dict[str, tuple[str, float]] = {}
        for coin in coins:
            pos = float(pos_df.loc[t, coin])
            signals_dict[coin] = ("BUY" if pos > 0 else "SELL", pos)

        vols = {coin: float(rolling_vols[coin].loc[t]) for coin in coins}

        portfolio_dd = portfolio_equity / running_max_equity - 1.0

        # Track when the drawdown brake fires
        if portfolio_dd < _DD_BRAKE_LEVEL:
            dd_brake_dates.append(t_date)

        pw = allocate_portfolio(
            signals=signals_dict,
            realized_vols=vols,
            eligible_coins=eligible,
            portfolio_dd=portfolio_dd,
        )
        for coin in coins:
            weight_df.loc[t, coin] = pw.weights.get(coin, 0.0)

        if i > oos_start:
            t_prev = common_idx[i - 1]
            daily_ret_t = sum(
                weight_df.loc[t_prev, coin] * float(daily_returns[coin].loc[t]) for coin in coins
            )
            portfolio_equity *= 1 + daily_ret_t
            running_max_equity = max(running_max_equity, portfolio_equity)

    # ── 5. Compute portfolio net returns ──────────────────────────────────────
    ret_df = pd.DataFrame({coin: daily_returns[coin] for coin in coins}, index=common_idx)

    gross_portfolio = (weight_df * ret_df).sum(axis=1)
    turnover = weight_df.diff().abs().sum(axis=1).fillna(0.0)
    cost_series = turnover * costs
    net_portfolio = gross_portfolio - cost_series
    net_oos = net_portfolio.iloc[oos_start:].dropna()

    # Per-coin weighted return contributions (OOS)
    per_coin_weighted_returns: dict[str, pd.Series] = {
        coin: (weight_df[coin] * ret_df[coin]).iloc[oos_start:]
        for coin in coins
    }

    # ── 6. Equal-weight BH baseline ───────────────────────────────────────────
    ew_weights: list[float] = []
    for t in net_oos.index:
        t_date = t.date() if hasattr(t, "date") else t
        eligible = universe.eligible_coins(t_date)
        n_elig = len(eligible)
        if n_elig > 0:
            daily_ew = sum(
                (1.0 / n_elig) * float(daily_returns[coin].get(t, 0.0))
                for coin in eligible
                if coin in daily_returns
            )
            ew_weights.append(daily_ew)
        else:
            ew_weights.append(0.0)

    bh_ew_returns = pd.Series(ew_weights, index=net_oos.index)

    avg_exposure_val = float(weight_df.iloc[oos_start:].sum(axis=1).mean())
    exposure_matched = bh_ew_returns * avg_exposure_val

    # ── 7. Compute metrics ────────────────────────────────────────────────────
    strat_sharpe = _sharpe(net_oos)
    strat_calmar = _calmar(net_oos)
    strat_cagr = _cagr(net_oos)
    strat_max_dd = _max_drawdown(net_oos)

    bh_sharpe = _sharpe(bh_ew_returns)
    bh_calmar = _calmar(bh_ew_returns)
    bh_max_dd = _max_drawdown(bh_ew_returns)
    bh_cagr = _cagr(bh_ew_returns)

    em_sharpe = _sharpe(exposure_matched)
    em_calmar = _calmar(exposure_matched)
    em_max_dd = _max_drawdown(exposure_matched)
    em_cagr = _cagr(exposure_matched)

    beats_bh = bool(strat_sharpe > bh_sharpe and strat_calmar > bh_calmar)
    beats_em = bool(strat_sharpe > em_sharpe and strat_calmar > em_calmar)

    n_rebalances = int((turnover.iloc[oos_start:] > 0.0).sum())

    # ── 8. Per-coin stats ─────────────────────────────────────────────────────
    oos_weights = weight_df.iloc[oos_start:]
    per_coin: dict[str, PortfolioCoinStats] = {}
    for coin in coins:
        coin_weights = oos_weights[coin]
        days_in = int((coin_weights > 0.0).sum())
        avg_w = float(coin_weights[coin_weights > 0.0].mean()) if days_in > 0 else 0.0
        per_coin[coin] = PortfolioCoinStats(avg_weight=avg_w, days_in_portfolio=days_in)

    # ── 9. PIT universe transparency dict ────────────────────────────────────
    pit_universe_str = {
        coin: first_d.isoformat()
        for coin, first_d in universe.first_eligible_dates.items()
        if coin in coins
    }

    equity_curve = _equity_curve(net_oos)

    report = PortfolioBacktestReport(
        coins=coins,
        sharpe=strat_sharpe,
        calmar=strat_calmar,
        max_dd=strat_max_dd,
        cagr=strat_cagr,
        avg_exposure=avg_exposure_val,
        n_rebalances=n_rebalances,
        beats_equal_weight_bh=beats_bh,
        beats_exposure_matched=beats_em,
        equity_curve=equity_curve,
        per_coin_stats=per_coin,
        pit_universe=pit_universe_str,
        costs=costs,
    )

    return {
        "report": report,
        "dd_brake_dates": dd_brake_dates,
        "per_coin_weighted_returns": per_coin_weighted_returns,
        "bh_ew_returns": bh_ew_returns,
        "exposure_matched_returns": exposure_matched,
        "net_oos_returns": net_oos,
        "bh_sharpe": bh_sharpe,
        "bh_calmar": bh_calmar,
        "bh_max_dd": bh_max_dd,
        "bh_cagr": bh_cagr,
        "em_sharpe": em_sharpe,
        "em_calmar": em_calmar,
        "em_max_dd": em_max_dd,
        "em_cagr": em_cagr,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_portfolio_walkforward(
    price_data: dict[str, pd.DataFrame],
    universe: UniverseMembership,
    costs: float = 0.001,
    min_train: int = 252,
    step: int = 63,
    ma_window: int = 100,
) -> PortfolioBacktestReport:
    """Expanding-window portfolio walk-forward backtest with PIT universe.

    Args:
        price_data:  {coin: DataFrame(close, volume)} — DatetimeIndex.
        universe:    PIT universe membership (already built from same price_data).
        costs:       Round-trip transaction cost per weight unit (default 0.1 %).
        min_train:   Warm-up bars before any position is taken (default 252).
        step:        Kept for API consistency; ignored for indicator strategy.
        ma_window:   MA window for the consensus signal (default 100).

    Returns:
        PortfolioBacktestReport (Pydantic).
    """
    return _walkforward_core(price_data, universe, costs, min_train, ma_window)["report"]


def run_portfolio_walkforward_with_details(
    price_data: dict[str, pd.DataFrame],
    universe: UniverseMembership,
    costs: float = 0.001,
    min_train: int = 252,
    step: int = 63,
    ma_window: int = 100,
) -> tuple[PortfolioBacktestReport, dict[str, Any]]:
    """Like run_portfolio_walkforward but also returns internal details.

    The second element (details dict) contains:
        dd_brake_dates            list[date] — OOS dates when DD brake fired
        per_coin_weighted_returns dict[str, pd.Series] — w_i * r_i per coin
        bh_ew_returns             pd.Series — equal-weight BH daily returns
        exposure_matched_returns  pd.Series — exposure-matched baseline
        net_oos_returns           pd.Series — net portfolio daily returns
        bh_sharpe / bh_calmar / bh_max_dd / bh_cagr  — EW-BH metrics
        em_sharpe / em_calmar / em_max_dd / em_cagr   — Exposure-matched metrics
    """
    data = _walkforward_core(price_data, universe, costs, min_train, ma_window)
    report = data.pop("report")
    return report, data


# ---------------------------------------------------------------------------
# Helper: empty report for edge cases
# ---------------------------------------------------------------------------


def _empty_report(
    coins: list[str],
    costs: float,
    universe: UniverseMembership,
) -> PortfolioBacktestReport:
    return PortfolioBacktestReport(
        coins=coins,
        sharpe=0.0,
        calmar=0.0,
        max_dd=0.0,
        cagr=0.0,
        avg_exposure=0.0,
        n_rebalances=0,
        beats_equal_weight_bh=False,
        beats_exposure_matched=False,
        equity_curve=[],
        per_coin_stats={},
        pit_universe={},
        costs=costs,
    )
