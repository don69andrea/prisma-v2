#!/usr/bin/env python3
"""
PRISMA V4-2 Befund: Meta-Label Walk-Forward gegen echte yfinance-Daten.

Fragestellung: Verbessert der Meta-Filter die risiko-adjustierte Performance
(Sharpe/Calmar) ODER senkt er nur Trades/Kosten ohne Mehrwert?

Methodik:
- Expanding-Window Walk-Forward: min_train=252, step=21, embargo=5
- OOS Meta-Filter: für jeden Test-Fold Classifier auf Trainings-Daten gefittet,
  Vorhersage auf OOS-Daten — kein Look-Ahead
- Vergleich: OOS-Periode MIT vs. OHNE Meta-Filter
- Kosten: 0.1% pro Turnover-Einheit, netto
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings

import numpy as np
import pandas as pd
import yfinance as yf

from backend.application.signals.indicators import atr, macd, rsi, sma
from backend.application.signals.meta_label import (
    build_meta_features,
    fit_meta_classifier,
    triple_barrier_labels,
)
from backend.application.backtest.walkforward import run_walkforward_with_details

warnings.filterwarnings("ignore")

# ── Konfiguration ─────────────────────────────────────────────────────────────

COINS = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"]
START_DATE = "2019-01-01"
END_DATE = "2024-12-31"

MIN_TRAIN = 252
STEP = 21
EMBARGO = 5
COSTS = 0.001  # 0.1 % pro Turnover-Einheit


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def download_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Lade OHLCV-Daten via yfinance."""
    raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError(f"Keine Daten für {ticker}")
    # yfinance 0.2+ kann MultiIndex-Spalten zurückgeben
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.columns = [c.lower() for c in raw.columns]
    raw.index = pd.to_datetime(raw.index)
    if raw.index.tz is not None:
        raw.index = raw.index.tz_localize(None)
    return raw[["open", "high", "low", "close", "volume"]].dropna()


def build_primary_signals(df: pd.DataFrame) -> pd.Series:
    """Erzeuge Consensus-Signal (SMA/RSI/MACD 2-of-3) für die ganze Periode.

    Signal[t] = 1 wenn ≥2 von 3 Indikatoren bullisch — basiert nur auf
    Daten ≤ t (kein Look-Ahead). shift(1) wird in run_walkforward_with_details
    angewendet bevor die Position berechnet wird.
    """
    close = df["close"]
    sma_100 = sma(close, window=100)
    rsi_14 = rsi(close, window=14)
    _, _, macd_hist = macd(close)

    ma_sig = (close > sma_100).fillna(0).astype(float)
    rsi_sig = (rsi_14 > 50).fillna(0).astype(float)
    macd_sig = (macd_hist > 0).fillna(0).astype(float)

    consensus = ((ma_sig + rsi_sig + macd_sig) >= 2).astype(float)
    return consensus


def build_oos_meta_filter(
    df: pd.DataFrame,
    min_train: int = MIN_TRAIN,
    step: int = STEP,
    embargo: int = EMBARGO,
) -> pd.Series:
    """Baue OOS Meta-Filter via Expanding-Window Walk-Forward.

    Für jeden Fold:
      - Trainiere LogReg-Classifier auf train=[0:start]
      - Embargo: überspringe Bars [start:start+embargo]
      - Vorhersage auf OOS=[start+embargo:start+embargo+step]
      - meta_filter[oos_bars] = Classifier-Vorhersage {0, 1}

    Kein Look-Ahead: Classifier verwendet nur Daten < test_start.
    """
    from sklearn.base import BaseEstimator

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Meta-Features aufbauen (build_meta_features wendet shift(1) intern an)
    meta_df = df.copy()
    meta_df["ma_signal"] = (close > sma(close, 100)).fillna(0).astype(float)
    meta_df["rsi_signal"] = (rsi(close, 14) > 50).fillna(0).astype(float)
    _, _, _macd_hist = macd(close)
    meta_df["macd_signal"] = (_macd_hist > 0).fillna(0).astype(float)

    X_full = build_meta_features(meta_df)
    # vol_pred / momentum_rank sind optional in build_meta_features → all-NaN wenn absent.
    # Fülle mit neutralen Werten damit dropna() nicht alle Zeilen löscht.
    X_full["vol_pred"] = X_full["vol_pred"].fillna(0.0)
    X_full["momentum_rank"] = X_full["momentum_rank"].fillna(0.0)

    # Triple-Barrier-Labels: y=1 wenn obere Barriere getroffen (Long-Trade profitable)
    y_raw = triple_barrier_labels(close, high, low)
    y_binary = (y_raw == 1).astype(int)

    # Alignierung: gemeinsame gültige Bars ohne NaN
    aligned = pd.concat([X_full, y_binary.rename("__y__")], axis=1).dropna()
    n = len(aligned)

    meta_filter = pd.Series(np.nan, index=df.index, dtype=float)

    n_folds = 0
    for start in range(min_train, n - step - embargo + 1, step):
        train = aligned.iloc[:start]
        test_start_idx = start + embargo
        test_end_idx = test_start_idx + step
        if test_end_idx > n:
            break

        test = aligned.iloc[test_start_idx:test_end_idx]
        X_train = train.drop(columns=["__y__"])
        y_train = train["__y__"]
        X_test = test.drop(columns=["__y__"])

        if len(y_train.unique()) < 2:
            # Nicht genug Klassen → Trades zulassen (konservative Fallback-Wahl)
            meta_filter.loc[test.index] = 1.0
            n_folds += 1
            continue

        model_info = fit_meta_classifier(X_train, y_train, model="logreg")
        clf = model_info["model"]
        assert isinstance(clf, BaseEstimator)
        preds = clf.predict(X_test.values).astype(float)
        meta_filter.loc[test.index] = preds
        n_folds += 1

    print(f"    OOS-Folds: {n_folds}")
    return meta_filter


def compute_total_costs(net_returns: pd.Series, gross_returns: pd.Series) -> float:
    """Summe der Transaktionskosten = gross - net."""
    return float((gross_returns - net_returns).sum())


def run_comparison(
    prices: pd.DataFrame,
    primary_signals: pd.Series,
    meta_filter: pd.Series,
    costs: float = COSTS,
) -> dict:
    """Vergleiche Backtest MIT vs. OHNE Meta-Filter auf der OOS-Periode."""

    oos_start = meta_filter.first_valid_index()
    oos_end = meta_filter.last_valid_index()
    if oos_start is None or oos_end is None:
        raise ValueError("Keine OOS-Vorhersagen vorhanden")

    # Beide Backtests laufen auf derselben OOS-Periode
    prices_oos = prices.loc[oos_start:oos_end]
    signals_oos = primary_signals.loc[oos_start:oos_end]
    filter_oos = meta_filter.loc[oos_start:oos_end].fillna(0.0)

    result_off = run_walkforward_with_details(
        prices=prices_oos,
        signals=signals_oos,
        costs=costs,
        meta_filter=None,
    )
    result_on = run_walkforward_with_details(
        prices=prices_oos,
        signals=signals_oos,
        costs=costs,
        meta_filter=filter_oos,
    )

    costs_off = compute_total_costs(result_off["net_returns"], result_off["gross_returns"])
    costs_on = compute_total_costs(result_on["net_returns"], result_on["gross_returns"])

    return {
        "oos_start": oos_start,
        "oos_end": oos_end,
        "oos_bars": len(prices_oos),
        "filter_coverage_pct": float(filter_oos.mean() * 100),
        "without_filter": {
            "sharpe": result_off["strategy_sharpe"],
            "calmar": result_off["strategy_calmar"],
            "max_dd": result_off["strategy_max_dd"],
            "cagr": result_off["strategy_cagr"],
            "n_trades": result_off["n_trades"],
            "total_costs": costs_off,
        },
        "with_filter": {
            "sharpe": result_on["strategy_sharpe"],
            "calmar": result_on["strategy_calmar"],
            "max_dd": result_on["strategy_max_dd"],
            "cagr": result_on["strategy_cagr"],
            "n_trades": result_on["n_trades"],
            "total_costs": costs_on,
        },
    }


# ── Hauptprogramm ─────────────────────────────────────────────────────────────


def main() -> dict:
    print("=" * 70)
    print("PRISMA V4-2 Meta-Label Eval — echte yfinance-Daten (OOS)")
    print(f"Periode: {START_DATE} bis {END_DATE}")
    print(f"Walk-Forward: min_train={MIN_TRAIN}, step={STEP}, embargo={EMBARGO}")
    print(f"Kosten: {COSTS * 100:.2f}% per Turnover-Einheit, netto")
    print("=" * 70)

    results: dict[str, dict] = {}

    for coin in COINS:
        print(f"\n{'─' * 60}")
        print(f"  {coin}")

        try:
            df = download_ohlcv(coin, START_DATE, END_DATE)
            n_bars = len(df)
            print(f"  Bars: {n_bars}  ({df.index[0].date()} – {df.index[-1].date()})")

            if n_bars < MIN_TRAIN + STEP + EMBARGO + 100:
                print(f"  SKIP: zu wenig Daten")
                continue

            primary_signals = build_primary_signals(df)
            print(f"  Primary-Signal ON: {primary_signals.mean() * 100:.1f}% der Zeit")

            meta_filter = build_oos_meta_filter(df)
            n_valid = int(meta_filter.notna().sum())
            pct_on = float(meta_filter.eq(1.0).sum()) / n_valid * 100 if n_valid > 0 else 0.0
            print(f"  Meta-Filter OOS-Bars: {n_valid} | Filter=1: {pct_on:.1f}%")

            cmp = run_comparison(df, primary_signals, meta_filter)
            results[coin] = cmp

            off = cmp["without_filter"]
            on = cmp["with_filter"]

            print()
            print(f"    OOS: {cmp['oos_start'].date()} – {cmp['oos_end'].date()} "
                  f"({cmp['oos_bars']} Bars)")
            print()
            hdr = f"    {'Metrik':<16} {'OHNE Filter':>12} {'MIT Filter':>12} {'Delta':>10}"
            sep = f"    {'─' * 52}"
            print(hdr)
            print(sep)
            print(f"    {'Sharpe':<16} {off['sharpe']:>12.3f} {on['sharpe']:>12.3f}"
                  f" {on['sharpe'] - off['sharpe']:>+10.3f}")
            print(f"    {'Calmar':<16} {off['calmar']:>12.3f} {on['calmar']:>12.3f}"
                  f" {on['calmar'] - off['calmar']:>+10.3f}")
            print(f"    {'MaxDD':<16} {off['max_dd']:>11.2%} {on['max_dd']:>11.2%}"
                  f" {on['max_dd'] - off['max_dd']:>+9.2%}")
            print(f"    {'CAGR':<16} {off['cagr']:>11.2%} {on['cagr']:>11.2%}"
                  f" {on['cagr'] - off['cagr']:>+9.2%}")
            print(f"    {'Trades':<16} {off['n_trades']:>12d} {on['n_trades']:>12d}"
                  f" {on['n_trades'] - off['n_trades']:>+10d}")
            print(f"    {'Kosten (Σ)':<16} {off['total_costs']:>12.4f} {on['total_costs']:>12.4f}"
                  f" {on['total_costs'] - off['total_costs']:>+10.4f}")

        except Exception as exc:
            import traceback
            print(f"  FEHLER: {exc}")
            traceback.print_exc()

    # ── Gesamtbefund ──────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("GESAMTBEFUND V4-2")
    print("=" * 70)
    print()

    sharpe_wins = 0
    calmar_wins = 0
    n = len(results)

    for coin, cmp in results.items():
        off = cmp["without_filter"]
        on = cmp["with_filter"]
        s_better = on["sharpe"] > off["sharpe"]
        c_better = on["calmar"] > off["calmar"]
        sharpe_wins += int(s_better)
        calmar_wins += int(c_better)
        tag = "BESSER" if (s_better and c_better) else ("GEMISCHT" if (s_better or c_better) else "SCHLECHTER")
        print(f"  {coin:<12}  Sharpe {'+' if s_better else '–'}  Calmar {'+' if c_better else '–'}  → {tag}")

    both_better = sum(
        1
        for cmp in results.values()
        if cmp["with_filter"]["sharpe"] > cmp["without_filter"]["sharpe"]
        and cmp["with_filter"]["calmar"] > cmp["without_filter"]["calmar"]
    )

    print()
    print(f"  Sharpe verbessert: {sharpe_wins}/{n}")
    print(f"  Calmar verbessert: {calmar_wins}/{n}")
    print(f"  Beide verbessert:  {both_better}/{n}")
    print()

    if both_better > n / 2:
        verdict = "POSITIV"
        detail = (
            "Meta-Filter verbessert Sharpe UND Calmar auf Mehrheit der Coins.\n"
            "→ Meta-Labeling hat belegten Mehrwert. Filter-ON als Default empfohlen."
        )
    elif sharpe_wins == n or calmar_wins == n:
        verdict = "SEKUNDÄR-POSITIV"
        detail = (
            "Meta-Filter verbessert Sharpe ODER Calmar konsistent, aber nicht beides.\n"
            "→ Sekundärer Mehrwert (Trades-/Kosten-Reduktion), kein klarer Performance-Gewinn."
        )
    else:
        verdict = "NEGATIV"
        detail = (
            "Meta-Filter verbessert weder Sharpe noch Calmar konsistent.\n"
            "→ KEIN belegter Mehrwert. Empfehlung: Meta-Label standardmäßig AUS."
        )

    print(f"  BEFUND: {verdict}")
    print(f"  {detail}")
    print()

    return results


if __name__ == "__main__":
    main()
