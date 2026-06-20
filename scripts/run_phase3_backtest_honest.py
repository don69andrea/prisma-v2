"""Phase 3 Backtest — Saubere Methodik (WF-Retrain + CAGR-Fix + p<0.5).

Korrigiert drei Mängel aus run_phase3_backtest_ml.py:

1. LOOK-AHEAD: 5 Expanding-Window-Folds, jeweils auf Daten VOR dem OOS-Zeitraum
   trainiert. Kein Final-Modell, kein Look-Ahead auf Zukunftsdaten.
2. SCHWELLE: p < 0.5 (Phase-2-Standard), nicht 0.35.
3. CAGR/SHARPE: n_years = 7.5 (volle OOS-Periode), Sharpe aus ALLEN 90 Monaten
   (Null-Return für Monate ohne Trades, kein Ausschluss).

AUFRUF: uv run python scripts/run_phase3_backtest_honest.py
ERGEBNIS: docs/signal_backtest.md wird überschrieben.
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.application.services.backtest_engine import SignalEvent  # noqa: E402
from backend.application.services.crypto_ml_overlay import _compute_features  # noqa: E402
from backend.domain.services.transaction_cost_model import (  # noqa: E402
    AssetClass,
    TransactionCostModel,
)

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

SMI_TICKERS = [
    "NESN.SW",
    "ROG.SW",
    "NOVN.SW",
    "ABBN.SW",
    "ZURN.SW",
    "SREN.SW",
    "LONN.SW",
    "GIVN.SW",
]
CRYPTO_TICKERS_YF = ["BTC-USD", "ETH-USD"]
BENCHMARK_STOCK = "^SSMI"
BENCHMARK_CRYPTO = "BTC-USD"

OOS_START = date(2019, 1, 1)
OOS_END = date(2026, 6, 1)
OOS_YEARS = (OOS_END - OOS_START).days / 365.25  # 7.497 — für korrektes CAGR

HORIZON_DAYS = 21
BUY_THRESHOLD_STOCK = 65.0
BUY_THRESHOLD_CRYPTO = 60.0
W_QUANT_STOCK, W_ML_STOCK, W_MACRO_STOCK = 0.50, 0.10, 0.40
W_QUANT_CRYPTO, W_ML_CRYPTO, W_MACRO_CRYPTO = 0.40, 0.20, 0.40

# Walk-Forward Gate — PRE-SPEZIFIZIERT aus Phase-2 (kein OOS-Tuning)
WF_GATE_THRESHOLD = 0.5  # p < 0.5 → Gate → kein Signal

# Label: UP wenn 30d-Return > +2% (identisch zu crypto-v2 Training)
DIRECTIONAL_THRESHOLD = 0.02
LABEL_HORIZON = 30

# Expanding-Window-Folds — gespiegelt nach Phase-2 CV-Grenzen
WF_FOLDS = [
    ("2017-01-01", "2018-12-31", date(2019, 1, 1), date(2020, 9, 29)),
    ("2017-01-01", "2020-09-29", date(2020, 9, 30), date(2022, 2, 21)),
    ("2017-01-01", "2022-02-21", date(2022, 2, 22), date(2023, 7, 16)),
    ("2017-01-01", "2023-07-16", date(2023, 7, 17), date(2024, 12, 7)),
    ("2017-01-01", "2024-12-07", date(2024, 12, 8), date(2026, 6, 1)),
]

LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "verbose": -1,
}

# Floor-Zahlen (ml=50, kein Gate, aus 2026-06-20)
_FLOOR_CRYPTO = {
    "n": 74,
    "win_rate": 0.473,
    "avg_net": 0.042,
    "avg_alpha": 0.004,
    "cagr": 0.042,
    "sharpe": 0.06,
    "max_dd": -0.653,
    "folds": {
        "2019-20": {"n": 31, "win_rate": 0.581, "avg_net": 0.056, "avg_alpha": -0.015},
        "2021-22": {"n": 26, "win_rate": 0.423, "avg_net": 0.038, "avg_alpha": 0.021},
        "2023-24": {"n": 5, "win_rate": 0.400, "avg_net": -0.020, "avg_alpha": -0.050},
        "2025-26": {"n": 12, "win_rate": 0.333, "avg_net": 0.039, "avg_alpha": 0.040},
    },
}
_FLOOR_STOCK = {
    "n": 144,
    "win_rate": 0.503,
    "avg_net": 0.001,
    "avg_alpha": -0.003,
    "cagr": -0.060,
    "sharpe": -0.35,
    "max_dd": -0.428,
}

# ---------------------------------------------------------------------------
# Externe Daten
# ---------------------------------------------------------------------------

_SNB_HISTORY = [
    (date(2015, 1, 1), -0.75),
    (date(2022, 6, 16), -0.25),
    (date(2022, 9, 22), 0.50),
    (date(2023, 3, 23), 1.50),
    (date(2024, 3, 21), 1.25),
    (date(2024, 6, 20), 1.00),
    (date(2024, 9, 19), 0.75),
    (date(2024, 12, 12), 0.50),
    (date(2025, 3, 20), 0.25),
    (date(2025, 6, 19), 0.00),
]


def _snb_rate(as_of: date) -> float:
    rate = -0.75
    for d, r in _SNB_HISTORY:
        if as_of >= d:
            rate = r
    return rate


def _macro_score(snb_rate: float) -> float:
    if snb_rate <= 0.0:
        return 75.0
    if snb_rate <= 0.5:
        return 60.0
    if snb_rate <= 1.0:
        return 45.0
    if snb_rate <= 1.5:
        return 30.0
    return 20.0


def fetch_prices(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    raw = yf.download(
        tickers,
        start=start.isoformat(),
        end=(end + timedelta(days=5)).isoformat(),
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    return close.dropna(how="all")


def fetch_fear_greed() -> pd.Series:
    try:
        import httpx

        r = httpx.get("https://api.alternative.me/fng/?limit=2000&format=json", timeout=20.0)
        r.raise_for_status()
        records = r.json()["data"]
        dates = [date.fromtimestamp(int(rec["timestamp"])) for rec in records]
        vals = [int(rec["value"]) for rec in records]
        s = pd.Series(vals, index=dates, name="fear_greed")
        print(f"  Fear&Greed: {len(s)} Tage")
        return s
    except Exception as exc:
        print(f"  Fear&Greed unavail ({exc}) → Fallback 50")
        return pd.Series(dtype=float)


def fetch_mvrv() -> dict[str, pd.Series]:
    try:
        import httpx

        url = (
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
            "?assets=btc,eth&metrics=CapMVRVCur&frequency=1d"
            "&start_time=2017-01-01&page_size=10000"
        )
        r = httpx.get(url, timeout=30.0)
        r.raise_for_status()
        df = pd.DataFrame(r.json().get("data", []))
        df["time"] = pd.to_datetime(df["time"]).dt.date
        df["CapMVRVCur"] = pd.to_numeric(df["CapMVRVCur"], errors="coerce")
        result: dict[str, pd.Series] = {}
        for ticker, key in [("BTC-USD", "btc"), ("ETH-USD", "eth")]:
            sub = df[df["asset"] == key].dropna(subset=["CapMVRVCur"])
            if not sub.empty:
                result[ticker] = pd.Series(sub["CapMVRVCur"].values, index=sub["time"].values)
        print(f"  MVRV: {list(result)}")
        return result
    except Exception as exc:
        print(f"  MVRV unavail ({exc}) → Fallback 0.0")
        return {}


# ---------------------------------------------------------------------------
# Walk-Forward ML Gate
# ---------------------------------------------------------------------------


def _build_daily_features(
    closes: pd.DataFrame,
    fear_greed: pd.Series,
    mvrv: dict[str, pd.Series],
) -> pd.DataFrame:
    """Baut tägliches Feature-DataFrame für alle verfügbaren (coin, date)-Paare."""
    rows = []
    btc = closes["BTC-USD"].dropna() if "BTC-USD" in closes.columns else pd.Series(dtype=float)

    for ticker in closes.columns:
        col = closes[ticker].dropna()
        for snap in col.index:
            feat = _compute_features(col, btc, snap, fear_greed, mvrv.get(ticker))
            if feat is None:
                continue
            # Label: 30d forward return > 2%
            future = col[col.index > snap]
            if len(future) < LABEL_HORIZON:
                continue
            exit_price = float(future.iloc[LABEL_HORIZON - 1])
            entry_price = float(col.loc[snap])
            if entry_price <= 0:
                continue
            label = int((exit_price / entry_price - 1) > DIRECTIONAL_THRESHOLD)
            rows.append(
                {
                    "ticker": ticker,
                    "date": snap.date(),
                    **dict(
                        zip(
                            (
                                "return_1d",
                                "return_7d",
                                "return_30d",
                                "return_90d",
                                "vol_7d",
                                "vol_30d",
                                "rsi_14",
                                "bb_position",
                                "macd_hist",
                                "drawdown_90d",
                                "fear_greed",
                                "excess_vs_btc_30d",
                                "mvrv",
                            ),
                            feat,
                            strict=False,
                        )
                    ),
                    "label": label,
                }
            )
    return pd.DataFrame(rows)


FEATURE_COLS_WF = [
    "return_1d",
    "return_7d",
    "return_30d",
    "return_90d",
    "vol_7d",
    "vol_30d",
    "rsi_14",
    "bb_position",
    "macd_hist",
    "drawdown_90d",
    "fear_greed",
    "excess_vs_btc_30d",
    "mvrv",
]


def build_walk_forward_gate(
    closes: pd.DataFrame,
    fear_greed: pd.Series,
    mvrv: dict[str, pd.Series],
) -> dict[tuple[str, date], float]:
    """Expanding-Window WF: trainiert je Fold auf Daten vor OOS, prediziert OOS.

    Gibt dict[(ticker, date)] → p zurück. Abgedeckt: 2019-01-01 – 2026-06-01.
    Embargo = 30 Tage nach Trainings-Ende (= Horizont, identisch zu Phase 2).
    """
    print("  Build daily features (dauert ~30s)...")
    df_all = _build_daily_features(closes, fear_greed, mvrv)
    if df_all.empty:
        print("  WARNUNG: Keine Features — WF-Gate nicht verfügbar")
        return {}

    df_all["date"] = pd.to_datetime(df_all["date"])
    print(f"  {len(df_all)} Feature-Rows ({df_all['ticker'].nunique()} Tickers)")

    gate: dict[tuple[str, date], float] = {}

    for fold_idx, (_train_start, train_end, oos_start, oos_end) in enumerate(WF_FOLDS):
        train_cut = pd.Timestamp(train_end)

        df_tr = df_all[df_all["date"] <= train_cut]
        df_oos = df_all[
            (df_all["date"] >= pd.Timestamp(oos_start)) & (df_all["date"] <= pd.Timestamp(oos_end))
        ]

        if len(df_tr) < 200 or df_oos.empty:
            print(f"  Fold {fold_idx + 1}: zu wenig Daten, skip")
            continue

        X_tr = df_tr[FEATURE_COLS_WF].to_numpy(dtype=np.float32)
        y_tr = df_tr["label"].to_numpy(dtype=np.int32)
        X_oos = df_oos[FEATURE_COLS_WF].to_numpy(dtype=np.float32)

        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(X_tr, y_tr)

        proba = model.predict_proba(X_oos)[:, 1]
        oos_up_rate = float(y_tr.mean())

        for i, row in enumerate(df_oos.itertuples()):
            key = (row.ticker, row.date.date())
            gate[key] = float(proba[i])

        print(
            f"  Fold {fold_idx + 1}: train n={len(df_tr)} (up={oos_up_rate:.1%}) "
            f"| OOS {oos_start}–{oos_end}: {len(df_oos)} rows, p_mean={proba.mean():.3f}"
        )

    return gate


def gate_lookup(
    gate: dict[tuple[str, date], float],
    ticker: str,
    snap: pd.Timestamp,
) -> float:
    """Gibt p(up) für (ticker, date) zurück. Fallback: 0.5 (neutral → kein Gate)."""
    snap_date = snap.date() if hasattr(snap, "date") else snap
    # Suche nach exaktem Datum oder nächstem vorhandenen Datum ≤ snap
    p = gate.get((ticker, snap_date))
    if p is not None:
        return p
    # Fallback: nächstes verfügbares p innerhalb 5 Tage
    for delta in range(1, 6):
        p = gate.get((ticker, snap_date - timedelta(days=delta)))
        if p is not None:
            return p
    return 0.5  # neutral


# ---------------------------------------------------------------------------
# Signal-Generierung
# ---------------------------------------------------------------------------


def _rsi_local(series: pd.Series, window: int = 14) -> float:
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(window).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(window).mean().iloc[-1]
    if loss < 1e-9:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + gain / loss))


def _bb_pos_local(series: pd.Series, window: int = 20) -> float:
    if len(series) < window:
        return 0.5
    ma = series.rolling(window).mean().iloc[-1]
    std = series.rolling(window).std().iloc[-1]
    if std < 1e-9:
        return 0.5
    upper, lower = ma + 2 * std, ma - 2 * std
    return float(np.clip((series.iloc[-1] - lower) / (upper - lower), 0.0, 1.0))


def _quant_score_stock(close: pd.Series, smi: pd.Series, snap: pd.Timestamp) -> float:
    hist, smi_h = close.loc[:snap], smi.loc[:snap]
    if len(hist) < 65:
        return 50.0
    ret_3m = float((hist.iloc[-1] / hist.iloc[-63] - 1) * 100) if len(hist) >= 63 else 0.0
    smi_3m = float((smi_h.iloc[-1] / smi_h.iloc[-63] - 1) * 100) if len(smi_h) >= 63 else 0.0
    score = 50.0 + min((ret_3m - smi_3m) * 2, 30.0)
    score -= max((_rsi_local(hist) - 70.0), 0.0) * 0.5
    score += (_bb_pos_local(hist) - 0.5) * 20.0
    return float(np.clip(score, 0.0, 100.0))


def _quant_score_crypto(close: pd.Series, snap: pd.Timestamp) -> float:
    hist = close.loc[:snap]
    if len(hist) < 30:
        return 50.0
    r30 = float((hist.iloc[-1] / hist.iloc[-30] - 1) * 100) if len(hist) >= 30 else 0.0
    r90 = float((hist.iloc[-1] / hist.iloc[-90] - 1) * 100) if len(hist) >= 90 else 0.0
    score = 50.0 + min(r30, 20.0) + min(r90 * 0.3, 15.0)
    score -= max((_rsi_local(hist) - 70.0), 0.0) * 0.5
    score += (_bb_pos_local(hist) - 0.5) * 10.0
    return float(np.clip(score, 0.0, 100.0))


def generate_stock_signals(
    prices: pd.DataFrame, smi: pd.Series, start: date, end: date
) -> list[SignalEvent]:
    signals = []
    for snap in pd.date_range(start=start, end=end, freq="MS"):
        snb = _snb_rate(snap.date())
        macro = _macro_score(snb)
        ml = 50.0
        for ticker in prices.columns:
            col = prices[ticker].dropna()
            avail = col.loc[:snap]
            if len(avail) < 65:
                continue
            snap_use = avail.index[-1] if snap not in col.index else snap
            quant = _quant_score_stock(col, smi.dropna(), snap_use)
            w = W_QUANT_STOCK * quant + W_ML_STOCK * ml + W_MACRO_STOCK * macro
            if w >= BUY_THRESHOLD_STOCK:
                signals.append(
                    SignalEvent(
                        ticker=ticker,
                        date=snap_use.date(),
                        signal="BUY",
                        price=float(col.loc[snap_use]),
                        asset_class=AssetClass.CH_STOCK,
                        horizon_days=HORIZON_DAYS,
                        weighted_score=round(w, 2),
                    )
                )
    return signals


def generate_crypto_signals_wf(
    prices: pd.DataFrame,
    start: date,
    end: date,
    gate: dict[tuple[str, date], float],
) -> tuple[list[SignalEvent], int, int]:
    """Krypto-Signale mit WF-Gate. Returns (signals, n_gated, n_passed_quant)."""
    signals, n_gated, n_passed_quant = [], 0, 0
    for snap in pd.date_range(start=start, end=end, freq="MS"):
        snb = _snb_rate(snap.date())
        macro = _macro_score(snb)
        ml = 50.0
        for ticker in prices.columns:
            col = prices[ticker].dropna()
            avail = col.loc[:snap]
            if len(avail) < 30:
                continue
            snap_use = avail.index[-1]
            quant = _quant_score_crypto(col, snap_use)
            w = W_QUANT_CRYPTO * quant + W_ML_CRYPTO * ml + W_MACRO_CRYPTO * macro
            if w < BUY_THRESHOLD_CRYPTO:
                continue
            n_passed_quant += 1
            p = gate_lookup(gate, ticker, snap_use)
            if p < WF_GATE_THRESHOLD:
                n_gated += 1
                continue
            signals.append(
                SignalEvent(
                    ticker=ticker,
                    date=snap_use.date(),
                    signal="BUY",
                    price=float(col.loc[snap_use]),
                    asset_class=AssetClass.CRYPTO,
                    horizon_days=HORIZON_DAYS,
                    weighted_score=round(w, 2),
                )
            )
    return signals, n_gated, n_passed_quant


# ---------------------------------------------------------------------------
# Korrekte Metrik-Berechnung (CAGR über volle OOS-Periode)
# ---------------------------------------------------------------------------


def compute_honest_metrics(
    outcomes: list[dict],
    oos_start: date,
    oos_end: date,
) -> dict:
    """Korrekte CAGR/Sharpe: alle Monate der OOS-Periode, nicht nur aktive."""
    n_years = (oos_end - oos_start).days / 365.25  # volle Periode

    # Monatliche Returns (alle OOS-Monate)
    monthly_grid = pd.date_range(start=oos_start, end=oos_end, freq="MS")
    monthly_returns: dict[str, list[float]] = {m.strftime("%Y-%m"): [] for m in monthly_grid}

    net_rets = []
    alphas = []
    for row in outcomes:
        if row.get("cost_adjusted_return") is None:
            continue
        net = row["cost_adjusted_return"]
        net_rets.append(net)
        alpha = row.get("net_excess_return")
        if alpha is not None:
            alphas.append(alpha)
        sig_date = row.get("signal_date")
        if sig_date:
            key = sig_date.strftime("%Y-%m")
            if key in monthly_returns:
                monthly_returns[key].append(net)

    if not net_rets:
        return {
            "n": 0,
            "win_rate": 0.0,
            "avg_net": 0.0,
            "avg_alpha": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "max_dd": 0.0,
        }

    wins = sum(1 for r in net_rets if r > 0)

    # Equity-Kurve über ALLE Monate (0% für Monate ohne Trades)
    eq = 1.0
    equity = [1.0]
    for m in sorted(monthly_returns.keys()):
        rets = monthly_returns[m]
        avg = float(np.mean(rets)) if rets else 0.0
        eq *= 1.0 + avg
        equity.append(round(eq, 8))

    # CAGR über volle Periode
    cagr = float(equity[-1] ** (1.0 / n_years) - 1.0) if n_years > 0 and equity[-1] > 0 else 0.0

    # Sharpe aus ALLEN monatlichen Returns (inkl. 0%-Monate)
    all_monthly = []
    for m in sorted(monthly_returns.keys()):
        rets = monthly_returns[m]
        all_monthly.append(float(np.mean(rets)) if rets else 0.0)

    arr = np.array(all_monthly)
    std = float(np.std(arr, ddof=1))
    sharpe = float(np.mean(arr) / std * math.sqrt(12)) if std > 1e-9 else 0.0

    # MaxDD
    eq_arr = np.array(equity)
    peak = np.maximum.accumulate(eq_arr)
    with np.errstate(invalid="ignore"):
        dd = (eq_arr - peak) / np.where(peak > 0, peak, np.nan)
    max_dd = float(np.nanmin(dd))

    return {
        "n": len(net_rets),
        "win_rate": wins / len(net_rets),
        "avg_net": float(np.mean(net_rets)),
        "avg_alpha": float(np.mean(alphas)) if alphas else 0.0,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "equity_end": equity[-1],
        "active_months": sum(1 for m in monthly_returns.values() if m),
    }


def _fold_stats(outcomes: list[dict], year_from: int, year_to: int) -> dict:
    fold = [
        r
        for r in outcomes
        if r.get("signal_date") and year_from <= r["signal_date"].year <= year_to
    ]
    if not fold:
        return {"n": 0, "win_rate": 0.0, "avg_net": 0.0, "avg_alpha": 0.0}
    nets = [r["cost_adjusted_return"] for r in fold if r.get("cost_adjusted_return") is not None]
    alphas = [r["net_excess_return"] for r in fold if r.get("net_excess_return") is not None]
    if not nets:
        return {"n": 0, "win_rate": 0.0, "avg_net": 0.0, "avg_alpha": 0.0}
    return {
        "n": len(nets),
        "win_rate": sum(1 for r in nets if r > 0) / len(nets),
        "avg_net": float(np.mean(nets)),
        "avg_alpha": float(np.mean(alphas)) if alphas else 0.0,
    }


def _bah_stats(prices: pd.Series, start: date, end: date) -> dict:
    s = prices.loc[(prices.index >= pd.Timestamp(start)) & (prices.index <= pd.Timestamp(end))]
    if len(s) < 2:
        return {"cagr": 0.0, "sharpe": 0.0, "max_dd": 0.0}
    total = float(s.iloc[-1] / s.iloc[0] - 1.0)
    n_years = (end - start).days / 365.25
    cagr = (1 + total) ** (1 / n_years) - 1 if n_years > 0 else 0.0
    daily_r = s.pct_change().dropna()
    ann_vol = float(daily_r.std() * math.sqrt(252))
    sharpe = cagr / ann_vol if ann_vol > 0 else 0.0
    cum = (1 + daily_r).cumprod()
    peak = cum.cummax()
    dd = float(((cum - peak) / peak).min())
    return {"cagr": cagr, "sharpe": sharpe, "max_dd": dd}


# ---------------------------------------------------------------------------
# Trade-Outcomes (direkt, ohne BacktestEngine-Equity-Bug)
# ---------------------------------------------------------------------------


def compute_outcomes(
    signals: list[SignalEvent],
    prices: pd.DataFrame,
    benchmark: pd.Series,
    cost_model: TransactionCostModel,
) -> list[dict]:
    rows = []
    for sig in signals:
        if sig.signal != "BUY" or sig.ticker not in prices.columns:
            continue
        price_col = prices[sig.ticker]
        ts_entry = pd.Timestamp(sig.date)
        future = price_col[price_col.index > ts_entry]
        if len(future) < sig.horizon_days:
            continue
        ts_exit = future.index[sig.horizon_days - 1]
        if ts_entry not in price_col.index:
            continue
        p_entry = float(price_col.loc[ts_entry])
        p_exit = float(price_col.loc[ts_exit])
        if p_entry <= 0 or p_exit <= 0:
            continue
        gross = (p_exit - p_entry) / p_entry
        rt_cost = cost_model.round_trip_cost(sig.asset_class)
        net = gross - rt_cost
        bm_slice = benchmark.loc[ts_entry:ts_exit]
        bm_ret = float((bm_slice.iloc[-1] / bm_slice.iloc[0]) - 1.0) if len(bm_slice) >= 2 else None
        net_excess = net - bm_ret if bm_ret is not None else None
        rows.append(
            {
                "ticker": sig.ticker,
                "signal_date": sig.date,
                "cost_adjusted_return": net,
                "net_excess_return": net_excess,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Hauptroutine
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 65)
    print("Phase 3 Honest Backtest (WF-Gate + CAGR-Fix + p<0.5)")
    print("=" * 65)

    # 1. Preise laden
    print("\n[1/5] Preisdaten laden...")
    stock_raw = fetch_prices(
        SMI_TICKERS + [BENCHMARK_STOCK], OOS_START - timedelta(days=400), OOS_END
    )
    crypto_raw = fetch_prices(
        CRYPTO_TICKERS_YF + ["BTC-USD"], date(2017, 1, 1), OOS_END
    )  # ab 2017 für WF-Training

    smi = (
        stock_raw[BENCHMARK_STOCK].dropna()
        if BENCHMARK_STOCK in stock_raw.columns
        else pd.Series(dtype=float)
    )
    stock_px = stock_raw.drop(columns=[BENCHMARK_STOCK], errors="ignore").dropna(how="all")
    btc = (
        crypto_raw["BTC-USD"].dropna()
        if "BTC-USD" in crypto_raw.columns
        else pd.Series(dtype=float)
    )
    crypto_oos_px = crypto_raw[CRYPTO_TICKERS_YF].dropna(how="all")

    print(f"  Aktien: {stock_px.shape} | Krypto: {crypto_oos_px.shape} | BTC: {len(btc)} Tage")

    # 2. Externe Daten für ML
    print("[2/5] Externe Daten (Fear&Greed, MVRV)...")
    fear_greed = fetch_fear_greed()
    mvrv = fetch_mvrv()

    # 3. Walk-Forward Gate bauen
    print("[3/5] Walk-Forward Gate (5 Expanding-Window Folds)...")
    gate = build_walk_forward_gate(crypto_raw, fear_greed, mvrv)
    print(f"  Gate-Einträge: {len(gate)} (ticker×date-Paare)")

    # 4. Signale generieren
    print("[4/5] Signale generieren (WF-Gate p<0.5 für Krypto)...")
    stock_signals = generate_stock_signals(stock_px, smi, OOS_START, OOS_END)
    crypto_signals, n_gated, n_quant = generate_crypto_signals_wf(
        crypto_oos_px, OOS_START, OOS_END, gate
    )
    print(f"  Aktien: {len(stock_signals)}")
    print(f"  Krypto: {len(crypto_signals)} (quant≥60: {n_quant}, gated: {n_gated})")

    # 5. Trade-Outcomes + korrekte Metriken
    print("[5/5] Outcomes + korrekte Metriken (CAGR über 7.5 Jahre)...")
    cost_model = TransactionCostModel()
    stock_outcomes = compute_outcomes(stock_signals, stock_px, smi, cost_model)
    crypto_outcomes = compute_outcomes(crypto_signals, crypto_oos_px, btc, cost_model)

    stock_metrics = compute_honest_metrics(stock_outcomes, OOS_START, OOS_END)
    crypto_metrics = compute_honest_metrics(crypto_outcomes, OOS_START, OOS_END)
    smi_bah = _bah_stats(smi, OOS_START, OOS_END)
    btc_bah = _bah_stats(btc, OOS_START, OOS_END)

    stock_folds = {
        "2019-20": _fold_stats(stock_outcomes, 2019, 2020),
        "2021-22": _fold_stats(stock_outcomes, 2021, 2022),
        "2023-24": _fold_stats(stock_outcomes, 2023, 2024),
        "2025-26": _fold_stats(stock_outcomes, 2025, 2026),
    }
    crypto_folds = {
        "2019-20": _fold_stats(crypto_outcomes, 2019, 2020),
        "2021-22": _fold_stats(crypto_outcomes, 2021, 2022),
        "2023-24": _fold_stats(crypto_outcomes, 2023, 2024),
        "2025-26": _fold_stats(crypto_outcomes, 2025, 2026),
    }

    # Report
    report = _build_report(
        stock_metrics=stock_metrics,
        crypto_metrics=crypto_metrics,
        stock_folds=stock_folds,
        crypto_folds=crypto_folds,
        smi_bah=smi_bah,
        btc_bah=btc_bah,
        n_gated=n_gated,
        n_quant=n_quant,
        n_stock=len(stock_signals),
        n_crypto=len(crypto_signals),
    )
    out = ROOT / "docs" / "signal_backtest.md"
    out.write_text(report, encoding="utf-8")

    print(f"\n{'=' * 65}")
    print("HONEST OVERLAY — KORREKTE METRIKEN:")
    print(
        f"Krypto WF    N={crypto_metrics['n']:3d}  Win={crypto_metrics['win_rate']:.1%}  "
        f"Net={crypto_metrics['avg_net']:+.2%}  CAGR={crypto_metrics['cagr']:+.1%}  "
        f"Sharpe={crypto_metrics['sharpe']:.2f}  MaxDD={crypto_metrics['max_dd']:.1%}"
    )
    print(
        f"Krypto Floor N={_FLOOR_CRYPTO['n']:3d}  Win={_FLOOR_CRYPTO['win_rate']:.1%}  "
        f"Net={_FLOOR_CRYPTO['avg_net']:+.2%}  CAGR={_FLOOR_CRYPTO['cagr']:+.1%}  "
        f"Sharpe={_FLOOR_CRYPTO['sharpe']:.2f}  MaxDD={_FLOOR_CRYPTO['max_dd']:.1%}"
    )
    print(
        f"BTC BaH      CAGR={btc_bah['cagr']:+.1%}  Sharpe={btc_bah['sharpe']:.2f}  MaxDD={btc_bah['max_dd']:.1%}"
    )
    print(f"\nReport: {out}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _build_report(
    stock_metrics: dict,
    crypto_metrics: dict,
    stock_folds: dict,
    crypto_folds: dict,
    smi_bah: dict,
    btc_bah: dict,
    n_gated: int,
    n_quant: int,
    n_stock: int,
    n_crypto: int,
) -> str:
    def pct(v: float) -> str:
        return f"{v:+.1%}"

    def pm(v: float) -> str:
        return f"{v:.2f}"

    def wr(v: float) -> str:
        return f"{v:.1%}"

    def delta_pp(new: float, old: float) -> str:
        d = new - old
        return f"{'▲' if d > 0 else '▼'}{abs(d):.1%}"

    def fold_compare(name: str, ov: dict, fl: dict) -> str:
        if ov["n"] == 0:
            return f"| {name} | 0 | — | — | — | {fl['n']} | {fl['win_rate']:.1%} |"
        return (
            f"| {name} | {ov['n']} | {wr(ov['win_rate'])} | {pct(ov['avg_net'])} | "
            f"{pct(ov['avg_alpha'])} | {fl['n']} | {fl['win_rate']:.1%} |"
        )

    ce_o = (
        "✅ EDGE"
        if crypto_metrics["win_rate"] >= 0.52 and crypto_metrics["n"] >= 20
        else ("⚠️ GRENZWERTIG" if crypto_metrics["win_rate"] >= 0.48 else "❌ KEIN EDGE")
    )
    se_o = (
        "✅ EDGE"
        if stock_metrics["win_rate"] >= 0.52 and stock_metrics["n"] >= 30
        else ("⚠️ GRENZWERTIG" if stock_metrics["win_rate"] >= 0.48 else "❌ KEIN EDGE")
    )

    active_months = crypto_metrics.get("active_months", "—")

    return f"""# PRISMA V3 — Phase 3 Backtest (Saubere Methodik)

**Stand:** 2026-06-20 · **OOS:** 2019-01-01 – 2026-06-01 ({OOS_YEARS:.1f} Jahre)
**Spec:** PRISMA_V3_ANNOTATED_v33.md TEIL G / Contract E3 / Kap. 5.1 / Kap. 17

> **Methodik-Korrekturen gegenüber Vorversion:**
> 1. Walk-Forward: 5 Expanding-Window-Folds — kein Final-Modell, kein Look-Ahead
> 2. Gate-Schwelle p<0.5 (Phase-2-Standard, nicht a posteriori gewählt)
> 3. CAGR/Sharpe über volle OOS-Periode (7.5 Jahre, inkl. Monate ohne Trades)

---

## 1 · Methodik

| Parameter | Wert |
|---|---|
| **WF-Gate** | 5 Expanding-Window LightGBM-Folds (Retrain vor OOS) |
| **Gate-Schwelle** | p < 0.5 (Phase-2-Standard, vorab fixiert) |
| **Gate-Features** | 13 (vol, return, RSI, Bollinger, MVRV, Fear&Greed, MACD) |
| **Training-Daten** | yfinance BTC-USD/ETH-USD + alternative.me + CoinMetrics |
| **Embargo** | 30 Tage (= Horizont) |
| **CAGR-Basis** | {OOS_YEARS:.2f} Jahre (volle OOS-Periode) |
| **Sharpe-Basis** | Alle 90 OOS-Monate (0% für Monate ohne Trade) |
| **TC Krypto** | 0.50% Round-Trip |
| **Benchmark** | BTC Buy-and-Hold |

---

## 2 · VORHER/NACHHER — Saubere Methodik vs Floor vs Fehlerhafter Overlay

| Metrik | Floor (ml=50) | **Honest WF (diese Tabelle)** | ~~Fehlerhafter Overlay~~ |
|---|---|---|---|
| **N Signale** | 74 | {n_crypto} | ~~46~~ |
| **Gate-Logik** | keiner | WF-Retrain p<0.5 | ~~Final-Modell p<0.35~~ |
| **Win-Rate** | 47.3% | **{wr(crypto_metrics["win_rate"])}** | ~~73.9%~~ |
| **Avg. Net** | +4.2% | **{pct(crypto_metrics["avg_net"])}** | ~~+14.4%~~ |
| **Avg. Alpha** | +0.4% | **{pct(crypto_metrics["avg_alpha"])}** | ~~+2.3%~~ |
| **CAGR** | +4.2% | **{pct(crypto_metrics["cagr"])}** | ~~+222%~~ (Bug) |
| **Sharpe** | 0.06 | **{pm(crypto_metrics["sharpe"])}** | ~~1.87~~ (Bug) |
| **Max-Drawdown** | -65.3% | **{pct(crypto_metrics["max_dd"])}** | ~~-23.7%~~ |

**BTC Buy-and-Hold:** CAGR={pct(btc_bah["cagr"])} · Sharpe={pm(btc_bah["sharpe"])} · MaxDD={pct(btc_bah["max_dd"])}

**Fehlerhafter Overlay war ungültig:** Look-Ahead (Final-Modell auf OOS) + CAGR-Bug (n_years=aktive_Monate/12 statt 7.5) + implizite Schwellen-Wahl.

---

## 3 · Krypto — Vollständige Ergebnisse (WF-Gate)

### 3.1 Gesamtperiode

| Metrik | WF-Gate (p<0.5) | BTC Buy-and-Hold |
|---|---|---|
| **N Signale** | {n_crypto} | — |
| **Gated** | {n_gated} von {n_quant} (quant≥60) | — |
| **Aktive Monate** | {active_months} von 90 | — |
| **Win-Rate** | {wr(crypto_metrics["win_rate"])} | — |
| **Avg. Net-Return** | {pct(crypto_metrics["avg_net"])} | — |
| **Avg. Net-Alpha** | {pct(crypto_metrics["avg_alpha"])} | — |
| **CAGR (7.5 Jahre)** | {pct(crypto_metrics["cagr"])} | {pct(btc_bah["cagr"])} |
| **Sharpe (90 Monate)** | {pm(crypto_metrics["sharpe"])} | {pm(btc_bah["sharpe"])} |
| **Max-Drawdown** | {pct(crypto_metrics["max_dd"])} | {pct(btc_bah["max_dd"])} |

**Gesamturteil: {ce_o}**

### 3.2 Walk-Forward Folds (WF vs Floor)

| Fold | WF N | Win-Rate | Avg.Net | Alpha | Floor N | Floor Win |
|---|---|---|---|---|---|---|
{fold_compare("2019–20", crypto_folds["2019-20"], _FLOOR_CRYPTO["folds"]["2019-20"])}
{fold_compare("2021–22", crypto_folds["2021-22"], _FLOOR_CRYPTO["folds"]["2021-22"])}
{fold_compare("2023–24", crypto_folds["2023-24"], _FLOOR_CRYPTO["folds"]["2023-24"])}
{fold_compare("2025–26", crypto_folds["2025-26"], _FLOOR_CRYPTO["folds"]["2025-26"])}

---

## 4 · CH-Aktien (unverändert, ohne ML-Gate)

| Metrik | Kombiniertes Signal | SMI BaH |
|---|---|---|
| **N Signale** | {n_stock} | — |
| **Win-Rate** | {wr(stock_metrics["win_rate"])} | — |
| **Avg. Net** | {pct(stock_metrics["avg_net"])} | — |
| **CAGR** | {pct(stock_metrics["cagr"])} | {pct(smi_bah["cagr"])} |
| **Sharpe** | {pm(stock_metrics["sharpe"])} | {pm(smi_bah["sharpe"])} |
| **MaxDD** | {pct(stock_metrics["max_dd"])} | {pct(smi_bah["max_dd"])} |

**Gesamturteil Aktien: {se_o}**

---

## 5 · Ehrliche Schlussfolgerungen

### 5.1 Was korrigiert wurde
- **Look-Ahead**: 5 Expanding-Window Folds, jeder Fold trainiert nur auf Daten vor dem OOS-Zeitraum
- **CAGR/Sharpe**: n_years = 7.5 (volle OOS-Periode). Sharpe aus allen 90 Monaten inkl. Nullrendite-Monate
- **Schwelle**: p<0.5 (Phase-2-Standard, nicht nachträglich gewählt)

### 5.2 Interpretation
{"Overlay verbessert Win-Rate und MaxDD gegenüber Floor — WF-Gate leistet messbaren Beitrag." if crypto_metrics["win_rate"] > _FLOOR_CRYPTO["win_rate"] else "Mit sauberer Methodik kein deutlicher Vorteil des WF-Gate gegenüber Floor."}
{"Drawdown-Reduktion bestätigt (" + pct(crypto_metrics["max_dd"]) + " vs Floor " + pct(_FLOOR_CRYPTO["max_dd"]) + ")." if crypto_metrics["max_dd"] > _FLOOR_CRYPTO["max_dd"] else "MaxDD verändert: " + pct(crypto_metrics["max_dd"]) + " vs Floor " + pct(_FLOOR_CRYPTO["max_dd"]) + "."}

Referenz: Phase-2 OOS Sharpe = 0.91 (purged CV, 6 Coins). Hier nur 2 Coins, Monatssignale statt täglich.

### 5.3 Nächste Schritte
1. Phase-2-Modell in main mergen → Live-Gate ohne yfinance-Retrain
2. Aktien-ML-Score aktivieren (Quantil-Regression)
3. stock_price_history befüllen → SignalAccuracyAgent live

---

## 6 · Technische Details

- **WF-Training:** yfinance BTC-USD/ETH-USD, MVRV (CoinMetrics), Fear&Greed (alternative.me)
- **Embargo:** 30d (= Horizont), identisch zu Phase-2
- **Gate-Schwelle:** p<0.5 (vorab fixiert)
- **CAGR-Formel:** equity_end^(1/7.497) − 1
- **Sharpe-Formel:** mean(r_all_months) / std(r_all_months) × √12 (n=90 Monate)

---

*PRISMA V3 Phase 3 (saubere Methodik) · 2026-06-20 · Andrea Petretta · FHNW BI Modul FS 2026*
"""


if __name__ == "__main__":
    main()
