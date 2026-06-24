"""robustness_check.py — PRISMA V4-4c Standalone Robustness Harness.

4 Stress-Test-Dimensionen gegen den V4-1 Edge:
  Dim 1 (D-03): Kosten-Sensitivitaet (costs: 0.1%, 0.2%, 0.5%)
  Dim 2 (D-04): Regime-Splits (Bear-2018, Bull-2021, Bear-2022, Bull-2023-24)
  Dim 3 (D-05): Volles Universum (10 Coins)
  Dim 4 (D-06): Parameter-Stabilitaet (SMA-Fenster: 50, 75, 100, 150, 200)

Standalone (kein DB-Zugriff). yfinance direkt. Rich-Konsolen-Ausgabe.
Importierbar fuer Tests: from scripts.robustness_check import build_signals, main

Ausfuehrung:
    source .venv/bin/activate
    python scripts/robustness_check.py
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np  # noqa: F401  (used via np.sqrt implicitly via indicators)
import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.table import Table

from backend.application.backtest.walkforward import (
    _calmar,
    _max_drawdown,
    _sharpe,
    run_walkforward_with_details,
)
from backend.application.signals.consensus import consensus_vote
from backend.application.signals.indicators import macd, rsi, sma
from backend.application.signals.sizing import vol_target_size

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Approximation label (User-Requirement: honest labeling)
# ---------------------------------------------------------------------------

_APPROX_NOTE: str = (
    "[engine-approximativ: consensus_vote() ECHT, "
    "Vol = rolling(21) statt fit_walkforward, standalone ohne DB]"
)

# ---------------------------------------------------------------------------
# Constants (D-03 / D-04 / D-05 / D-06)
# ---------------------------------------------------------------------------

_COST_LEVELS: list[float] = [0.001, 0.002, 0.005]
_MA_WINDOWS: list[int] = [50, 75, 100, 150, 200]
_DEFAULT_MA: int = 100
_DEFAULT_COST: float = 0.001
_MIN_ROWS: int = 315  # min_train=252 + step=63
_DATA_START: str = "2015-01-01"

_CRYPTO_UNIVERSE: list[str] = [
    "BTC-USD",
    "ETH-USD",
    "BNB-USD",
    "SOL-USD",
    "XRP-USD",
    "ADA-USD",
    "AVAX-USD",
    "MATIC-USD",
    "DOT-USD",
    "LINK-USD",
]

_COST_COINS: list[str] = ["BTC-USD", "ETH-USD"]
_PARAM_COINS: list[str] = ["BTC-USD", "ETH-USD"]

_REGIMES: list[dict[str, Any]] = [
    {"name": "Bear 2018", "start": "2018-01-01", "end": "2018-12-31"},
    {"name": "Bull 2021", "start": "2021-01-01", "end": "2021-12-31"},
    {"name": "Bear 2022", "start": "2022-01-01", "end": "2022-12-31"},
    {"name": "Bull 2023-24", "start": "2023-01-01", "end": "2024-12-31"},
]

# Coins not listed in 2018 (insufficient for Bear-2018 regime)
_NOT_LISTED_2018: set[str] = {"SOL-USD", "AVAX-USD", "DOT-USD", "MATIC-USD"}

# MATIC-USD was renamed to POL on 2025-03-24
_MATIC_END_DATE: str = "2025-03-24"

# ---------------------------------------------------------------------------
# Dataclasses (frozen=True per plan)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostResult:
    """Result for one coin at one cost level (Dim 1)."""

    coin: str
    cost_level: float
    strategy_sharpe: float
    strategy_calmar: float
    strategy_max_dd: float
    baseline_sharpe: float
    baseline_calmar: float
    bah_sharpe: float
    bah_calmar: float
    beats_exposure_matched: bool


@dataclass(frozen=True)
class RegimeResult:
    """Result for one coin in one market regime (Dim 2)."""

    coin: str
    regime_name: str
    strategy_sharpe: float
    strategy_calmar: float
    strategy_max_dd: float
    baseline_sharpe: float
    baseline_calmar: float
    bah_max_dd: float  # MaxDD Buy&Hold sliced to regime window — downside protection comparison
    oos_rows: int
    note: str = field(default="")


@dataclass(frozen=True)
class UniverseResult:
    """Result for one coin across the full universe (Dim 3)."""

    coin: str
    strategy_sharpe: float
    strategy_calmar: float
    strategy_max_dd: float
    baseline_sharpe: float
    baseline_calmar: float
    beats_exposure_matched: bool
    note: str = field(default="")


@dataclass(frozen=True)
class ParamResult:
    """Result for one coin at one SMA window setting (Dim 4)."""

    coin: str
    ma_window: int
    is_default: bool
    strategy_sharpe: float
    strategy_calmar: float
    strategy_max_dd: float
    beats_exposure_matched: bool


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _download(coin: str, start: str, end: str | None = None) -> pd.Series | None:
    """Download daily close prices for *coin* from yfinance.

    Returns a UTC-aware pd.Series of Close prices, or None if download fails
    or returns empty data.
    """
    try:
        raw = yf.download(coin, start=start, end=end, progress=False, auto_adjust=True)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("yfinance download failed for %s: %s", coin, exc)
        return None

    if len(raw) == 0:
        return None

    close = raw["Close"].squeeze()
    close.index = pd.DatetimeIndex(close.index).tz_localize("UTC")
    return close


def _bah_metrics(close: pd.Series) -> tuple[float, float, float]:
    """Compute Buy-and-Hold metrics via walk-forward engine.

    Uses all-ones signals (always invested) with minimal costs=0.0001.

    Returns:
        (bah_sharpe, bah_calmar, bah_max_dd) — callers must unpack all three.
    """
    prices_df = pd.DataFrame({"close": close})
    bah_signals = pd.Series(1.0, index=close.index)
    details = run_walkforward_with_details(prices_df, bah_signals, costs=0.0001)
    net = details["net_returns"]
    return _sharpe(net), _calmar(net), _max_drawdown(net)


def build_signals(close: pd.Series, ma_window: int = 100) -> pd.Series:
    """Build a combined position signal with vol-targeting sizing.

    Applies shift(1) to binary signals BEFORE consensus_vote to prevent
    look-ahead (D-09). Uses rolling(21) vol approximation (D-10).

    Args:
        close: UTC-aware daily Close price series.
        ma_window: SMA window for the trend component (default 100).

    Returns:
        pd.Series of position sizes (0 to 1.5), same index as *close*.
    """
    sma_val = sma(close, window=ma_window)
    rsi_14 = rsi(close, window=14)
    _, _, macd_hist = macd(close)

    # shift(1) BEFORE consensus — D-09 look-ahead guard
    ma_s = (close > sma_val).astype(float).shift(1).fillna(0.0)
    rsi_s = (rsi_14 > 50).astype(float).shift(1).fillna(0.0)
    macd_s = (macd_hist > 0).astype(float).shift(1).fillna(0.0)

    signals_df = pd.DataFrame({"ma_signal": ma_s, "rsi_signal": rsi_s, "macd_signal": macd_s})

    # consensus_vote() is the REAL implementation from backend (not inline logic)
    consensus = consensus_vote(signals_df)

    # Rolling(21) vol approximation — D-10 (fit_walkforward forbidden in harness)
    rv = close.pct_change().rolling(21).std() * (252**0.5)
    rolling_vol = rv.shift(1).fillna(0.60)
    size_factors = rolling_vol.apply(lambda v: vol_target_size(v, target_vol=0.60, cap=1.5))

    return consensus.astype(float) * size_factors


# ---------------------------------------------------------------------------
# Dimension 1: Kosten-Sensitivitaet
# ---------------------------------------------------------------------------


def run_cost_sensitivity(
    coins: list[str] | None = None,
    cost_levels: list[float] | None = None,
    ma_window: int = _DEFAULT_MA,
) -> list[CostResult | dict[str, Any]]:
    """Run cost-sensitivity stress test (D-03).

    Args:
        coins: Coins to test (default: BTC-USD, ETH-USD).
        cost_levels: Cost levels to sweep (default: 0.001, 0.002, 0.005).
        ma_window: SMA window for signals (default 100).

    Returns:
        list of CostResult (success) or dict with status="insufficient" (not enough data).
    """
    if coins is None:
        coins = _COST_COINS
    if cost_levels is None:
        cost_levels = _COST_LEVELS

    results: list[CostResult | dict[str, Any]] = []

    for coin in coins:
        close = _download(coin, start=_DATA_START)
        if close is None:
            results.append(
                {"status": "download_failed", "coin": coin, "reason": "yfinance returned empty"}
            )
            continue

        if len(close) < _MIN_ROWS:
            results.append(
                {
                    "status": "insufficient",
                    "coin": coin,
                    "rows": len(close),
                    "reason": f"< {_MIN_ROWS} rows",
                }
            )
            continue

        bah_sharpe, bah_calmar, _bah_dd = _bah_metrics(close)
        signals = build_signals(close, ma_window=ma_window)
        prices_df = pd.DataFrame({"close": close})

        for cost in cost_levels:
            details = run_walkforward_with_details(prices_df, signals, costs=cost)
            results.append(
                CostResult(
                    coin=coin,
                    cost_level=cost,
                    strategy_sharpe=details["strategy_sharpe"],
                    strategy_calmar=details["strategy_calmar"],
                    strategy_max_dd=details["strategy_max_dd"],
                    baseline_sharpe=details["baseline_sharpe"],
                    baseline_calmar=details["baseline_calmar"],
                    bah_sharpe=bah_sharpe,
                    bah_calmar=bah_calmar,
                    beats_exposure_matched=details["beats_exposure_matched"],
                )
            )

    return results


# ---------------------------------------------------------------------------
# Dimension 2: Regime-Splits
# ---------------------------------------------------------------------------


def run_regime_splits(
    coins: list[str] | None = None,
    regimes: list[dict[str, Any]] | None = None,
    costs: float = _DEFAULT_COST,
    ma_window: int = _DEFAULT_MA,
) -> list[RegimeResult | dict[str, Any]]:
    """Run regime-split stress test (D-04).

    Downloads from _DATA_START to regime end (NOT just the regime window) so
    the walk-forward engine has sufficient training data before the OOS slice.

    Args:
        coins: Coins to test (default: full _CRYPTO_UNIVERSE).
        regimes: Regime definitions (default: 4 regimes from _REGIMES).
        costs: Transaction costs (default 0.001).
        ma_window: SMA window for signals (default 100).

    Returns:
        list of RegimeResult (success) or dict with status indicating failure reason.
    """
    if coins is None:
        coins = _CRYPTO_UNIVERSE
    if regimes is None:
        regimes = _REGIMES

    results: list[RegimeResult | dict[str, Any]] = []

    for coin in coins:
        for regime in regimes:
            regime_name = regime["name"]
            regime_start = regime["start"]
            regime_end = regime["end"]

            # Bear-2018: SOL/AVAX/DOT/MATIC not listed yet
            if regime_name == "Bear 2018" and coin in _NOT_LISTED_2018:
                results.append(
                    {
                        "status": "insufficient",
                        "coin": coin,
                        "regime": regime_name,
                        "rows": 0,
                        "reason": "not listed in 2018",
                    }
                )
                continue

            # MATIC-USD ends 2025-03-24 (renamed to POL)
            note = ""
            download_end = regime_end
            if coin == "MATIC-USD" and regime_end > _MATIC_END_DATE:
                download_end = _MATIC_END_DATE
                note = "MATIC-USD ends 2025-03-24 (renamed POL)"

            # Download from DATA_START to regime end (anti-pattern: NOT just regime window)
            close = _download(coin, start=_DATA_START, end=download_end)
            if close is None:
                results.append(
                    {
                        "status": "download_failed",
                        "coin": coin,
                        "regime": regime_name,
                        "reason": "yfinance returned empty",
                    }
                )
                continue

            if len(close) < _MIN_ROWS:
                results.append(
                    {
                        "status": "insufficient",
                        "coin": coin,
                        "regime": regime_name,
                        "rows": len(close),
                        "reason": f"< {_MIN_ROWS} rows",
                    }
                )
                continue

            signals = build_signals(close, ma_window=ma_window)
            prices_df = pd.DataFrame({"close": close})

            details = run_walkforward_with_details(prices_df, signals, costs=costs)
            net = details["net_returns"]
            baseline = details["baseline_returns"]

            # Buy&Hold baseline via all-ones signals
            bah_details = run_walkforward_with_details(
                prices_df, pd.Series(1.0, index=close.index), costs=0.0001
            )

            # Slice OOS returns to regime window
            mask = (net.index >= regime_start) & (net.index <= regime_end)
            regime_net = net[mask]
            regime_base = baseline[mask]

            bah_net = bah_details["net_returns"]
            bah_mask = (bah_net.index >= regime_start) & (bah_net.index <= regime_end)
            regime_bah = bah_net[bah_mask]

            if len(regime_net) < 21:
                results.append(
                    {
                        "status": "no_oos_in_regime",
                        "coin": coin,
                        "regime": regime_name,
                        "oos_rows": len(regime_net),
                    }
                )
                continue

            results.append(
                RegimeResult(
                    coin=coin,
                    regime_name=regime_name,
                    strategy_sharpe=_sharpe(regime_net),
                    strategy_calmar=_calmar(regime_net),
                    strategy_max_dd=_max_drawdown(regime_net),
                    baseline_sharpe=_sharpe(regime_base),
                    baseline_calmar=_calmar(regime_base),
                    bah_max_dd=_max_drawdown(regime_bah),
                    oos_rows=len(regime_net),
                    note=note,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Dimension 3: Volles Universum
# ---------------------------------------------------------------------------


def run_universe(
    ma_window: int = _DEFAULT_MA,
    costs: float = _DEFAULT_COST,
) -> list[UniverseResult | dict[str, Any]]:
    """Run full-universe stress test (D-05).

    Tests all 10 coins in _CRYPTO_UNIVERSE. Coins with <_MIN_ROWS data are
    marked as insufficient (not silently skipped).

    Args:
        ma_window: SMA window for signals (default 100).
        costs: Transaction costs (default 0.001).

    Returns:
        list of UniverseResult (success) or dict with status field.
    """
    results: list[UniverseResult | dict[str, Any]] = []

    for coin in _CRYPTO_UNIVERSE:
        note = ""
        if coin == "MATIC-USD":
            note = "MATIC-USD ends 2025-03-24 (renamed POL)"

        close = _download(coin, start=_DATA_START)
        if close is None:
            results.append(
                {
                    "status": "download_failed",
                    "coin": coin,
                    "reason": "yfinance returned empty",
                    "note": note,
                }
            )
            continue

        if len(close) < _MIN_ROWS:
            results.append(
                {
                    "status": "insufficient",
                    "coin": coin,
                    "rows": len(close),
                    "reason": f"< {_MIN_ROWS} rows",
                    "note": note,
                }
            )
            continue

        signals = build_signals(close, ma_window=ma_window)
        prices_df = pd.DataFrame({"close": close})
        details = run_walkforward_with_details(prices_df, signals, costs=costs)

        results.append(
            UniverseResult(
                coin=coin,
                strategy_sharpe=details["strategy_sharpe"],
                strategy_calmar=details["strategy_calmar"],
                strategy_max_dd=details["strategy_max_dd"],
                baseline_sharpe=details["baseline_sharpe"],
                baseline_calmar=details["baseline_calmar"],
                beats_exposure_matched=details["beats_exposure_matched"],
                note=note,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Dimension 4: Parameter-Stabilitaet
# ---------------------------------------------------------------------------


def run_parameter_stability(
    coins: list[str] | None = None,
    ma_windows: list[int] | None = None,
    costs: float = _DEFAULT_COST,
) -> list[ParamResult | dict[str, Any]]:
    """Run parameter-stability stress test (D-06).

    Sweeps SMA windows [50, 75, 100, 150, 200]. Downloads data once per coin
    to avoid repeated network calls.

    Args:
        coins: Coins to test (default: BTC-USD, ETH-USD).
        ma_windows: SMA windows to sweep (default: _MA_WINDOWS).
        costs: Transaction costs (default 0.001).

    Returns:
        list of ParamResult (success) or dict with status field.
    """
    if coins is None:
        coins = _PARAM_COINS
    if ma_windows is None:
        ma_windows = _MA_WINDOWS

    results: list[ParamResult | dict[str, Any]] = []

    for coin in coins:
        # Download once per coin — avoid repeated downloads across window loop
        close = _download(coin, start=_DATA_START)
        if close is None:
            for window in ma_windows:
                results.append(
                    {
                        "status": "download_failed",
                        "coin": coin,
                        "ma_window": window,
                        "reason": "yfinance returned empty",
                    }
                )
            continue

        if len(close) < _MIN_ROWS:
            for window in ma_windows:
                results.append(
                    {
                        "status": "insufficient",
                        "coin": coin,
                        "ma_window": window,
                        "rows": len(close),
                        "reason": f"< {_MIN_ROWS} rows",
                    }
                )
            continue

        prices_df = pd.DataFrame({"close": close})

        for window in ma_windows:
            signals = build_signals(close, ma_window=window)
            details = run_walkforward_with_details(prices_df, signals, costs=costs)
            results.append(
                ParamResult(
                    coin=coin,
                    ma_window=window,
                    is_default=(window == _DEFAULT_MA),  # marks the D-01 anchor point
                    strategy_sharpe=details["strategy_sharpe"],
                    strategy_calmar=details["strategy_calmar"],
                    strategy_max_dd=details["strategy_max_dd"],
                    beats_exposure_matched=details["beats_exposure_matched"],
                )
            )

    return results


# ---------------------------------------------------------------------------
# Rich output functions (one per dimension)
# ---------------------------------------------------------------------------

console = Console()


def print_cost_table(results: list[CostResult | dict[str, Any]]) -> None:
    """Print Dimension 1 (cost sensitivity) as a Rich table."""
    table = Table(title="Dim 1: Kosten-Sensitivitaet", show_lines=True)
    table.add_column("Coin", style="cyan")
    table.add_column("Kosten", justify="right")
    table.add_column("Sharpe(Strat)", justify="right")
    table.add_column("Sharpe(Base)", justify="right")
    table.add_column("Calmar(Strat)", justify="right")
    table.add_column("MaxDD", justify="right")
    table.add_column("Edge?", justify="center")

    for r in results:
        if isinstance(r, dict):
            table.add_row(
                r.get("coin", "?"),
                "—",
                "—",
                "—",
                "—",
                "—",
                r.get("status", "?"),
            )
        else:
            table.add_row(
                r.coin,
                f"{r.cost_level:.3f}",
                f"{r.strategy_sharpe:.3f}",
                f"{r.baseline_sharpe:.3f}",
                f"{r.strategy_calmar:.3f}",
                f"{r.strategy_max_dd:.3f}",
                "[green]YES[/green]" if r.beats_exposure_matched else "[red]NO[/red]",
            )

    console.print(table)


def print_regime_table(results: list[RegimeResult | dict[str, Any]]) -> None:
    """Print Dimension 2 (regime splits) as a Rich table.

    Columns: Coin / Regime / Sharpe(Strat) / Calmar(Strat) / MaxDD(Strat) / MaxDD(B&H) / OOS-Rows / Status
    """
    table = Table(title="Dim 2: Regime-Splits", show_lines=True)
    table.add_column("Coin", style="cyan")
    table.add_column("Regime")
    table.add_column("Sharpe(Strat)", justify="right")
    table.add_column("Calmar(Strat)", justify="right")
    table.add_column("MaxDD(Strat)", justify="right")
    table.add_column("MaxDD(B&H)", justify="right")
    table.add_column("OOS-Rows", justify="right")
    table.add_column("Status")

    for r in results:
        if isinstance(r, dict):
            table.add_row(
                r.get("coin", "?"),
                r.get("regime", "?"),
                "—",
                "—",
                "—",
                "—",
                str(r.get("oos_rows", "—")),
                r.get("status", "?"),
            )
        else:
            status_str = r.note if r.note else "OK"
            table.add_row(
                r.coin,
                r.regime_name,
                f"{r.strategy_sharpe:.3f}",
                f"{r.strategy_calmar:.3f}",
                f"{r.strategy_max_dd:.3f}",
                f"{r.bah_max_dd:.3f}",
                str(r.oos_rows),
                status_str,
            )

    console.print(table)


def print_universe_table(results: list[UniverseResult | dict[str, Any]]) -> None:
    """Print Dimension 3 (full universe) as a Rich table."""
    table = Table(title="Dim 3: Universum (10 Coins)", show_lines=True)
    table.add_column("Coin", style="cyan")
    table.add_column("Sharpe(Strat)", justify="right")
    table.add_column("Sharpe(Base)", justify="right")
    table.add_column("Calmar(Strat)", justify="right")
    table.add_column("MaxDD", justify="right")
    table.add_column("Beats?", justify="center")
    table.add_column("Note")

    for r in results:
        if isinstance(r, dict):
            table.add_row(
                r.get("coin", "?"),
                "—",
                "—",
                "—",
                "—",
                r.get("status", "?"),
                r.get("note", ""),
            )
        else:
            table.add_row(
                r.coin,
                f"{r.strategy_sharpe:.3f}",
                f"{r.baseline_sharpe:.3f}",
                f"{r.strategy_calmar:.3f}",
                f"{r.strategy_max_dd:.3f}",
                "[green]YES[/green]" if r.beats_exposure_matched else "[red]NO[/red]",
                r.note,
            )

    console.print(table)


def print_param_table(results: list[ParamResult | dict[str, Any]]) -> None:
    """Print Dimension 4 (parameter stability) as a Rich table."""
    table = Table(title="Dim 4: Parameter-Stabilitaet (SMA-Fenster)", show_lines=True)
    table.add_column("Coin", style="cyan")
    table.add_column("Fenster", justify="right")
    table.add_column("Default?", justify="center")
    table.add_column("Sharpe", justify="right")
    table.add_column("Calmar", justify="right")
    table.add_column("MaxDD", justify="right")
    table.add_column("Beats?", justify="center")

    for r in results:
        if isinstance(r, dict):
            table.add_row(
                r.get("coin", "?"),
                str(r.get("ma_window", "?")),
                "—",
                "—",
                "—",
                "—",
                r.get("status", "?"),
            )
        else:
            table.add_row(
                r.coin,
                str(r.ma_window),
                "[bold]YES[/bold]" if r.is_default else "no",
                f"{r.strategy_sharpe:.3f}",
                f"{r.strategy_calmar:.3f}",
                f"{r.strategy_max_dd:.3f}",
                "[green]YES[/green]" if r.beats_exposure_matched else "[red]NO[/red]",
            )

    console.print(table)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main() -> dict[str, Any]:
    """Run all 4 stress-test dimensions and print Rich tables.

    Returns:
        dict with keys: cost_results, regime_results, universe_results, parameter_results
    """
    console.print(_APPROX_NOTE, style="italic dim")

    # ── Dimension 1: Kosten-Sensitivitaet ────────────────────────────────────
    console.rule("[bold]Dimension 1: Kosten-Sensitivitaet[/bold]")
    cost_results = run_cost_sensitivity()
    print_cost_table(cost_results)

    # ── Dimension 2: Regime-Splits ────────────────────────────────────────────
    console.rule("[bold]Dimension 2: Regime-Splits[/bold]")
    regime_results = run_regime_splits()
    print_regime_table(regime_results)

    # ── Dimension 3: Volles Universum ─────────────────────────────────────────
    console.rule("[bold]Dimension 3: Universum (10 Coins)[/bold]")
    universe_results = run_universe()
    print_universe_table(universe_results)

    # ── Dimension 4: Parameter-Stabilitaet ───────────────────────────────────
    console.rule("[bold]Dimension 4: Parameter-Stabilitaet[/bold]")
    parameter_results = run_parameter_stability()
    print_param_table(parameter_results)

    return {
        "cost_results": cost_results,
        "regime_results": regime_results,
        "universe_results": universe_results,
        "parameter_results": parameter_results,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
