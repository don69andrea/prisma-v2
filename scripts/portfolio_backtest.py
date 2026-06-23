"""V4-4b Portfolio Walk-Forward Backtest — standalone runner.

Fetches OHLCV from yfinance directly (no DB, no asyncio).
Runs the PIT-universe portfolio backtest and prints three tables:
  1. Portfolio vs EW-Buy&Hold vs Exposure-Matched
  2. Drawdown-Bremse activity in 2022
  3. Per-coin Sharpe contribution

Usage:
    python scripts/portfolio_backtest.py
    python scripts/portfolio_backtest.py --start 2018-01-01 --costs 0.002
    python scripts/portfolio_backtest.py --coins BTC-USD ETH-USD SOL-USD
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from backend.interfaces.rest.schemas.signals import PortfolioBacktestReport

_CRYPTO_UNIVERSE = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "BNB-USD",
    "XRP-USD",
    "ADA-USD",
    "AVAX-USD",
    "DOGE-USD",
    "LINK-USD",
    "DOT-USD",
]
_DEFAULT_START = "2018-01-01"
_DEFAULT_COSTS = 0.001  # 0.1 % round-trip


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------


def fetch_prices(symbols: list[str], start: str) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV synchronously from yfinance. Returns {coin: DataFrame(close, volume)}."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed — run: pip install yfinance", file=sys.stderr)
        sys.exit(1)

    price_data: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            df: pd.DataFrame = yf.download(sym, start=start, progress=False, auto_adjust=True)
            if df.empty:
                print(f"  Warning: no data for {sym}", file=sys.stderr)
                continue
            # Flatten MultiIndex columns (yfinance ≥ 0.2 with single ticker is flat already)
            if isinstance(df.columns, pd.MultiIndex):
                df = df.droplevel(1, axis=1)
            df.columns = [c.lower() for c in df.columns]
            df.index.name = "date"
            price_data[sym] = df[["close", "volume"]].copy()
        except Exception as exc:  # noqa: BLE001
            print(f"  Warning: failed to fetch {sym}: {exc}", file=sys.stderr)
    return price_data


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------


def _fmt_pct(v: float) -> str:
    return f"{v * 100:+.1f}%"


def _fmt_f(v: float, decimals: int = 2) -> str:
    return f"{v:.{decimals}f}"


def print_comparison_table(
    report: PortfolioBacktestReport,
    details: dict,
) -> None:
    """Table 1 — Portfolio vs EW-Buy&Hold vs Exposure-Matched."""

    # Strategy metrics come from the report
    strat = {
        "Sharpe": report.sharpe,
        "Calmar": report.calmar,
        "MaxDD": report.max_dd,
        "CAGR": report.cagr,
        "Avg-Exposure": report.avg_exposure,
    }
    bh = {
        "Sharpe": details["bh_sharpe"],
        "Calmar": details["bh_calmar"],
        "MaxDD": details["bh_max_dd"],
        "CAGR": details["bh_cagr"],
        "Avg-Exposure": 1.0,
    }
    em = {
        "Sharpe": details["em_sharpe"],
        "Calmar": details["em_calmar"],
        "MaxDD": details["em_max_dd"],
        "CAGR": details["em_cagr"],
        "Avg-Exposure": report.avg_exposure,
    }

    print("\n" + "=" * 64)
    print("  V4-4b Portfolio Backtest — Vergleich")
    print("=" * 64)
    header = f"{'Metrik':<18} {'Portfolio':>12} {'EW-Buy&Hold':>13} {'Exp-Matched':>13}"
    print(header)
    print("-" * 64)

    pct_keys = {"MaxDD", "CAGR", "Avg-Exposure"}
    for key in ["Sharpe", "Calmar", "MaxDD", "CAGR", "Avg-Exposure"]:
        fmt = _fmt_pct if key in pct_keys else _fmt_f
        s = fmt(strat[key])
        b = fmt(bh[key])
        e = fmt(em[key])
        print(f"{key:<18} {s:>12} {b:>13} {e:>13}")

    print("-" * 64)
    beats_bh = "JA ✓" if report.beats_equal_weight_bh else "NEIN ✗"
    beats_em = "JA ✓" if report.beats_exposure_matched else "NEIN ✗"
    print(f"  Schlägt EW-Buy&Hold:     {beats_bh}")
    print(f"  Schlägt Exp-Matched:     {beats_em}")
    print(f"  Rebalancierungen (OOS):  {report.n_rebalances}")
    print(f"  Transaktionskosten:      {report.costs * 100:.2f}% RT")
    print()


def print_dd_brake_table(dd_brake_dates: list[date]) -> None:
    """Table 2 — Drawdown-Bremse 2022."""
    print("=" * 64)
    print("  Drawdown-Bremse (portfolio_dd < -15 %)")
    print("=" * 64)

    dates_2022 = [d for d in dd_brake_dates if d.year == 2022]
    total = len(dd_brake_dates)
    total_2022 = len(dates_2022)

    print(f"  Ausgelöst gesamt (OOS): {total} Tage")
    print(f"  davon in 2022:          {total_2022} Tage")

    if dates_2022:
        print(f"  Erste Auslösung 2022:   {dates_2022[0].isoformat()}")
        print(f"  Letzte Auslösung 2022:  {dates_2022[-1].isoformat()}")

        # Monthly breakdown for 2022
        from collections import Counter

        monthly: Counter[str] = Counter(d.strftime("%Y-%m") for d in dates_2022)
        print("\n  Monatliche Aufschlüsselung 2022:")
        print(f"  {'Monat':<10} {'Tage':>6}")
        print("  " + "-" * 18)
        for month in sorted(monthly):
            print(f"  {month:<10} {monthly[month]:>6}")
    elif total == 0:
        print("  Bremse wurde nie ausgelöst.")
    else:
        print("  Bremse nicht in 2022 ausgelöst.")
    print()


def print_per_coin_table(
    report: PortfolioBacktestReport,
    per_coin_weighted_returns: dict[str, pd.Series],
) -> None:
    """Table 3 — Per-coin Sharpe contribution (w_i × r_i)."""
    from backend.application.backtest.walkforward import _sharpe  # type: ignore[attr-defined]

    print("=" * 64)
    print("  Per-Coin Sharpe-Beitrag  (Gewichtete Rendite-Serie)")
    print("=" * 64)
    print(f"  {'Coin':<12} {'Sharpe-Btr':>11} {'Avg-Weight':>11} {'Tage-im-PF':>11}")
    print("  " + "-" * 50)

    rows = []
    for coin in sorted(per_coin_weighted_returns):
        series = per_coin_weighted_returns[coin]
        sh = _sharpe(series) if series.abs().sum() > 0 else 0.0
        stats = report.per_coin_stats.get(coin)
        avg_w = stats.avg_weight if stats else 0.0
        days = stats.days_in_portfolio if stats else 0
        rows.append((coin, sh, avg_w, days))

    # Sort by Sharpe contribution descending
    rows.sort(key=lambda x: x[1], reverse=True)

    for coin, sh, avg_w, days in rows:
        print(f"  {coin:<12} {sh:>+11.3f} {avg_w * 100:>10.1f}% {days:>11}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="V4-4b Portfolio Walk-Forward Backtest (yfinance, kein DB)"
    )
    parser.add_argument(
        "--start",
        default=_DEFAULT_START,
        help=f"Start-Datum YYYY-MM-DD (default: {_DEFAULT_START})",
    )
    parser.add_argument(
        "--costs",
        type=float,
        default=_DEFAULT_COSTS,
        help=f"Round-trip Kosten als Dezimalzahl (default: {_DEFAULT_COSTS})",
    )
    parser.add_argument(
        "--coins",
        nargs="+",
        default=_CRYPTO_UNIVERSE,
        metavar="SYMBOL",
        help="Coin-Symbole (default: 10-Coin-Universum)",
    )
    args = parser.parse_args(argv)

    print(f"\nFetching {len(args.coins)} Coins ab {args.start} via yfinance…")
    price_data = fetch_prices(args.coins, args.start)

    if not price_data:
        print("Keine Daten erhalten. Abbruch.", file=sys.stderr)
        sys.exit(1)

    print(f"Erhalten: {len(price_data)} Coins — {', '.join(sorted(price_data))}")

    from backend.application.backtest.portfolio_walkforward import (
        run_portfolio_walkforward_with_details,
    )
    from backend.application.backtest.universe import UniverseMembership

    universe = UniverseMembership(price_data)
    print(f"Starte Portfolio Walk-Forward (Kosten={args.costs * 100:.2f}%)…\n")

    report, details = run_portfolio_walkforward_with_details(price_data, universe, costs=args.costs)

    print_comparison_table(report, details)
    print_dd_brake_table(details["dd_brake_dates"])
    print_per_coin_table(report, details["per_coin_weighted_returns"])

    print("PIT-Universum Eligibility-Daten:")
    for coin, first_date in sorted(report.pit_universe.items()):
        print(f"  {coin:<12}  ab {first_date}")
    print()


if __name__ == "__main__":
    main()
