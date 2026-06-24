"""V4-4c Robustheits-/Stresstest der V4-1-Signal-Engine.

Fragestellungen:
  1. Hält der Edge bei höheren Kosten (0.1 / 0.2 / 0.5 %)?
  2. Über das volle Top-10-Universum (synthetische Modell-Coins)?
  3. Bei Parameter-Variation (MA-Fenster: 50 / 100 / 200)?

Läuft auf synthetischen Daten — kein Live-DB-Zugriff nötig.
Für echte Daten: ersetze _make_coin_prices() durch yfinance-Fetch.

Usage:
    python scripts/robustness_analysis.py
    python scripts/robustness_analysis.py --json        # JSON output
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

_COIN_SPECS: dict[str, tuple[float, float, float]] = {
    # coin_id: (drift_daily, vol_daily, trend_strength)
    "BTC-USD": (0.0010, 0.022, 1.2),
    "ETH-USD": (0.0009, 0.026, 1.1),
    "SOL-USD": (0.0008, 0.035, 1.0),
    "BNB-USD": (0.0007, 0.025, 0.9),
    "XRP-USD": (0.0006, 0.030, 0.8),
    "ADA-USD": (0.0005, 0.032, 0.7),
    "AVAX-USD": (0.0006, 0.038, 0.9),
    "DOGE-USD": (0.0004, 0.045, 0.6),
    "LINK-USD": (0.0007, 0.033, 0.9),
    "DOT-USD": (0.0005, 0.034, 0.7),
}

_N_DAYS = 1800  # ~5 years of daily data


def _make_coin_prices(coin: str, n: int = _N_DAYS, seed: int = 0) -> pd.DataFrame:
    """Synthetic OHLCV series for a coin.  close×volume gives $100M+ from day 1."""
    drift, vol_d, trend_strength = _COIN_SPECS.get(coin, (0.0007, 0.030, 0.8))
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift * trend_strength, vol_d, n)
    close = 100.0 * np.cumprod(1 + returns)
    # Volume such that dollar_vol is large (enables PIT membership from day 1)
    volume = rng.uniform(1e6, 3e6, n)  # 1M–3M units × close ≈ $100M+
    idx = pd.date_range("2019-01-01", periods=n, freq="D")
    return pd.DataFrame({"close": close, "volume": volume}, index=idx)


# ---------------------------------------------------------------------------
# Signal construction (replicates V4-1 MA-consensus logic without DB)
# ---------------------------------------------------------------------------


def _compute_ma_signal(close: pd.Series, window: int) -> pd.Series:
    ma = close.rolling(window, min_periods=window).mean()
    return (close > ma).astype(float)


def _compute_rsi_signal(close: pd.Series, window: int = 14) -> pd.Series:
    diff = close.diff(1)
    up = diff.where(diff > 0, 0.0)
    down = (-diff).where(diff < 0, 0.0)
    rs = up.ewm(alpha=1 / window, adjust=False).mean() / down.ewm(
        alpha=1 / window, adjust=False
    ).mean().replace(0, np.nan)
    rsi_val = 100 - 100 / (1 + rs)
    return (rsi_val > 50).astype(float).fillna(0.0)


def _compute_macd_signal(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return (macd_line > signal_line).astype(float)


def _make_consensus_signal(prices: pd.DataFrame, ma_window: int = 100) -> pd.Series:
    """2-of-3 vote: MA(ma_window) + MACD + RSI."""
    close = prices["close"]
    ma_sig = _compute_ma_signal(close, ma_window)
    rsi_sig = _compute_rsi_signal(close)
    macd_sig = _compute_macd_signal(close)
    vote = (ma_sig + rsi_sig + macd_sig) / 3.0
    return (vote >= 0.5).astype(float)  # ≥ 2/3 active


# ---------------------------------------------------------------------------
# Walk-forward helper (imports from application layer)
# ---------------------------------------------------------------------------


def _run_wf(prices: pd.DataFrame, signal: pd.Series, costs: float) -> dict[str, float]:
    """Thin wrapper around run_walkforward_with_details."""
    from backend.application.backtest.walkforward import run_walkforward_with_details

    d = run_walkforward_with_details(prices, signal, costs=costs)
    return {
        "sharpe": d["strategy_sharpe"],
        "calmar": d["strategy_calmar"],
        "max_dd": d["strategy_max_dd"],
        "baseline_sharpe": d["baseline_sharpe"],
        "baseline_calmar": d["baseline_calmar"],
        "beats": d["beats_exposure_matched"],
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


@dataclass
class RobustnessRow:
    coin: str
    ma_window: int
    costs_pct: float
    sharpe: float
    calmar: float
    max_dd: float
    baseline_sharpe: float
    baseline_calmar: float
    beats: bool


def run_robustness_analysis(
    coins: list[str] | None = None,
    ma_windows: list[int] | None = None,
    cost_levels: list[float] | None = None,
) -> list[RobustnessRow]:
    if coins is None:
        coins = list(_COIN_SPECS.keys())
    if ma_windows is None:
        ma_windows = [50, 100, 200]
    if cost_levels is None:
        cost_levels = [0.001, 0.002, 0.005]  # 0.1 / 0.2 / 0.5 %

    rows: list[RobustnessRow] = []
    for i, coin in enumerate(coins):
        prices = _make_coin_prices(coin, seed=i)
        for ma_w in ma_windows:
            signal = _make_consensus_signal(prices, ma_window=ma_w)
            for costs in cost_levels:
                res = _run_wf(prices, signal, costs=costs)
                rows.append(
                    RobustnessRow(
                        coin=coin,
                        ma_window=ma_w,
                        costs_pct=costs * 100,
                        sharpe=round(res["sharpe"], 4),
                        calmar=round(res["calmar"], 4),
                        max_dd=round(res["max_dd"], 4),
                        baseline_sharpe=round(res["baseline_sharpe"], 4),
                        baseline_calmar=round(res["baseline_calmar"], 4),
                        beats=bool(res["beats"]),
                    )
                )
    return rows


def _print_summary(rows: list[RobustnessRow]) -> None:
    print("\n=== V4-4c Robustness Analysis (synthetic data) ===\n")
    print(
        f"{'Coin':<12} {'MA':>4} {'Cost%':>6} {'Sharpe':>8} {'BL_Sh':>8} {'Calmar':>8} {'BL_Ca':>8} {'MaxDD':>8} {'Beats':>6}"
    )
    print("-" * 76)
    for r in rows:
        print(
            f"{r.coin:<12} {r.ma_window:>4} {r.costs_pct:>6.1f}"
            f" {r.sharpe:>8.3f} {r.baseline_sharpe:>8.3f}"
            f" {r.calmar:>8.3f} {r.baseline_calmar:>8.3f}"
            f" {r.max_dd:>8.3f} {'YES' if r.beats else 'NO':>6}"
        )

    beats_total = sum(r.beats for r in rows)
    total = len(rows)
    beats_pct = 100 * beats_total / total if total else 0
    print(f"\nBeats exposure-matched: {beats_total}/{total} ({beats_pct:.0f}%)")

    # Per cost-level summary
    for cost in sorted({r.costs_pct for r in rows}):
        sub = [r for r in rows if r.costs_pct == cost]
        b = sum(r.beats for r in sub)
        print(f"  Cost {cost:.1f}%: {b}/{len(sub)} beats")


def main() -> None:
    parser = argparse.ArgumentParser(description="V4-4c Robustness analysis")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    rows = run_robustness_analysis()

    if args.json:
        print(json.dumps([asdict(r) for r in rows], indent=2))
    else:
        _print_summary(rows)


if __name__ == "__main__":
    main()
