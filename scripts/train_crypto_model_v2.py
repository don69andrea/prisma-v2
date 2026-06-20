"""Training v2: LightGBM Krypto-ML — Risikoadjustiert (PRISMA V3).

Verbesserungen gegenüber v1:
  - Horizont H=30d (statt 7d), tägliche Snapshots (mehr Daten)
  - Embargo=30 Tage (= Horizont, strikt)
  - MVRV via Coin Metrics Community API (BTC/ETH, kein Key, Fallback 0.0)
  - Risikoadjustierte Bewertung: Sharpe, Max-Drawdown, Calmar Ratio
  - Equity-Kurve: monatliches Rebalancing (überlappungsfreie Periodenerträge)
  - Bear-Market-2022 Subperiode separat ausgewiesen

KEIN Deployment. Nur Bericht in docs/ml_eval_crypto_v2.md.

Aufruf: uv run python scripts/train_crypto_model_v2.py [--folds 5]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import numpy.typing as npt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("train_crypto_v2")

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
DOCS_DIR = ROOT / "docs"
MODELS_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

COINS = ["BTC", "ETH", "SOL", "ADA", "BNB", "XRP"]
ALTCOINS = ["ETH", "SOL", "ADA", "BNB", "XRP"]
MVRV_COINS = {"BTC": "btc", "ETH": "eth"}

TRANSACTION_COST_RT = 0.003  # 0.3% Round-Trip
DIRECTIONAL_THRESHOLD = 0.02  # UP wenn 30d > +2%
HORIZON = 30
EMBARGO_DAYS = 30  # = Horizont

FEATURE_COLS = (
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
)
FEATURE_HASH = hashlib.sha256(",".join(FEATURE_COLS).encode()).hexdigest()[:8]

BEAR_MARKET_START = date(2022, 1, 1)
BEAR_MARKET_END = date(2022, 12, 31)


# ---------------------------------------------------------------------------
# Technische Indikatoren
# ---------------------------------------------------------------------------


def _rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).rolling(window).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(window).mean().iloc[-1]
    if loss == 0:
        return 100.0
    return float(100.0 - 100.0 / (1 + gain / loss))


def _bb_position(close: pd.Series, window: int = 20) -> float:
    if len(close) < window:
        return 0.5
    ma = close.rolling(window).mean().iloc[-1]
    std = close.rolling(window).std().iloc[-1]
    upper, lower = ma + 2 * std, ma - 2 * std
    if upper - lower < 1e-9:
        return 0.5
    return float(np.clip((close.iloc[-1] - lower) / (upper - lower), 0.0, 1.0))


def _macd_hist(close: pd.Series) -> float:
    if len(close) < 35:
        return 0.0
    ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
    macd_line = ema12 - ema26
    # Einzel-Wert als Signal-Proxy
    return float(macd_line - (macd_line * 0.9 + (ema12 - ema26) * 0.1))


def _drawdown(close: pd.Series, window: int = 90) -> float:
    tail = close.tail(window)
    peak = tail.max()
    if peak < 1e-9:
        return 0.0
    return float((close.iloc[-1] - peak) / peak)


# ---------------------------------------------------------------------------
# Daten: MVRV via Coin Metrics Community API
# ---------------------------------------------------------------------------


def _fetch_mvrv_coinmetrics() -> dict[str, pd.Series]:
    """Lädt MVRV (Market Value / Realized Value) für BTC und ETH.

    Coin Metrics Community API — kostenlos, kein API-Key.
    Fallback: leere Series → Feature-Wert 0.0 (Neutral).
    """
    import httpx

    result: dict[str, pd.Series] = {}
    assets_str = ",".join(MVRV_COINS.values())
    url = (
        "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
        f"?assets={assets_str}&metrics=CapMVRVCur&frequency=1d"
        "&start_time=2017-01-01&page_size=10000"
    )
    try:
        log.info("Lade MVRV (Coin Metrics Community API) …")
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        if not rows:
            log.warning("MVRV: Keine Daten — Fallback 0.0")
            return result

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"]).dt.date
        df["CapMVRVCur"] = pd.to_numeric(df["CapMVRVCur"], errors="coerce")

        for coin, cm_key in MVRV_COINS.items():
            sub = df[df["asset"] == cm_key].dropna(subset=["CapMVRVCur"])
            if sub.empty:
                log.warning("MVRV: Keine Daten für %s", coin)
                continue
            s = pd.Series(sub["CapMVRVCur"].values, index=sub["time"].values, name=coin)
            result[coin] = s
            log.info("MVRV %s: %d Tage (%s → %s)", coin, len(s), s.index[0], s.index[-1])

        # Nächste Seite falls vorhanden
        if "next_page_token" in resp.json():
            log.info("MVRV: Nur erste Seite geladen (reicht für Backtest)")

    except Exception as exc:
        log.warning("MVRV-API nicht erreichbar (%s) — Feature bleibt 0.0", exc)

    return result


def _step_lookup(series: pd.Series, snap_date: date, default: float = 0.0) -> float:
    """Letzte bekannte Beobachtung am oder vor snap_date (Step-Funktion)."""
    if series is None or len(series) == 0:
        return default
    idx = series.index
    before = [d for d in idx if d <= snap_date]
    if not before:
        return default
    return float(series[before[-1]])


# ---------------------------------------------------------------------------
# Fear & Greed historisch
# ---------------------------------------------------------------------------


def _fetch_fear_greed() -> pd.Series:
    import httpx

    try:
        log.info("Lade Fear&Greed-Historie (alternative.me) …")
        resp = httpx.get("https://api.alternative.me/fng/?limit=2000&format=json", timeout=20.0)
        resp.raise_for_status()
        records = resp.json()["data"]
        dates = [date.fromtimestamp(int(r["timestamp"])) for r in records]
        values = [int(r["value"]) for r in records]
        s = pd.Series(values, index=dates, name="fear_greed")
        log.info("Fear&Greed: %d Tage (%s → %s)", len(s), min(dates), max(dates))
        return s
    except Exception as exc:
        log.warning("Fear&Greed-API nicht erreichbar (%s) — Fallback 50", exc)
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# Features (PIT-korrekt)
# ---------------------------------------------------------------------------


def _compute_features(
    close: pd.Series,
    btc_close: pd.Series,
    fg: pd.Series,
    mvrv_map: dict[str, pd.Series],
    ticker: str,
    snap: pd.Timestamp,
) -> dict[str, float] | None:
    past = close[close.index <= snap]
    btc_past = btc_close[btc_close.index <= snap]
    if len(past) < 120:
        return None

    def ret(n: int) -> float:
        return float(past.iloc[-1] / past.iloc[-n] - 1) if len(past) > n else 0.0

    def vol(n: int) -> float:
        if len(past) < n + 1:
            return 0.0
        dr = past.tail(n + 1).pct_change().dropna()
        return float(dr.std() * np.sqrt(365))

    btc_ret30 = float(btc_past.iloc[-1] / btc_past.iloc[-30] - 1) if len(btc_past) > 30 else 0.0

    snap_date = snap.date() if hasattr(snap, "date") else snap
    fg_val = _step_lookup(fg, snap_date, 50.0) if not fg.empty else 50.0

    mvrv_val = 0.0
    if ticker in mvrv_map and not mvrv_map[ticker].empty:
        mvrv_val = _step_lookup(mvrv_map[ticker], snap_date, 0.0)

    return {
        "return_1d": ret(1),
        "return_7d": ret(7),
        "return_30d": ret(30),
        "return_90d": ret(90),
        "vol_7d": vol(7),
        "vol_30d": vol(30),
        "rsi_14": _rsi(past.tail(60)),
        "bb_position": _bb_position(past.tail(30)),
        "macd_hist": _macd_hist(past.tail(60)),
        "drawdown_90d": _drawdown(past, 90),
        "fear_greed": fg_val,
        "excess_vs_btc_30d": ret(30) - btc_ret30,
        "mvrv": mvrv_val,
    }


# ---------------------------------------------------------------------------
# Dataset aus DB
# ---------------------------------------------------------------------------


async def _load_coin(ticker: str) -> pd.Series:
    from sqlalchemy import text

    from backend.infrastructure.persistence.session import get_session_factory

    factory = get_session_factory()
    async with factory() as sess:
        r = await sess.execute(
            text(
                "SELECT timestamp::date, close FROM crypto_price_history "
                "WHERE ticker = :t AND interval = '1d' ORDER BY timestamp ASC"
            ),
            {"t": ticker},
        )
        rows = r.fetchall()
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([row[0] for row in rows])
    return pd.Series([float(row[1]) for row in rows], index=idx, name=ticker)


def _target(close: pd.Series, btc: pd.Series, snap: pd.Timestamp) -> dict[str, Any]:
    future = close[close.index > snap]
    btc_future = btc[btc.index > snap]
    if len(future) < HORIZON or len(btc_future) < HORIZON:
        return {"fwd_return": None, "target_dir": None}
    fwd = float(future.iloc[HORIZON - 1] / future.iloc[0] - 1)
    return {
        "fwd_return": fwd,
        "target_dir": int(fwd > DIRECTIONAL_THRESHOLD),
    }


async def build_dataset_crypto_v2(coins: list[str] = COINS) -> pd.DataFrame:
    btc = await _load_coin("BTC")
    fg = _fetch_fear_greed()
    mvrv_map = _fetch_mvrv_coinmetrics()

    price_map: dict[str, pd.Series] = {"BTC": btc}
    for coin in coins:
        if coin != "BTC":
            price_map[coin] = await _load_coin(coin)
        log.info("Geladen: %s (%d Tage)", coin, len(price_map.get(coin, btc)))

    records = []
    for coin in coins:
        close = price_map.get(coin)
        if close is None or close.empty:
            log.warning("Keine Daten für %s", coin)
            continue

        start = close.index[max(0, 120)]
        end = close.index[-HORIZON - 5]
        # Tägliche Snapshots
        for snap in pd.date_range(start=start, end=end, freq="1D"):
            feats = _compute_features(close, btc, fg, mvrv_map, coin, snap)
            if feats is None:
                continue
            tgt = _target(close, btc, snap)
            if tgt["target_dir"] is None:
                continue
            records.append({"ticker": coin, "snap_date": snap.date(), **feats, **tgt})

    df = pd.DataFrame(records)
    log.info(
        "Dataset v2: %d Zeilen, %d Coins, %s → %s",
        len(df),
        df["ticker"].nunique() if not df.empty else 0,
        df["snap_date"].min() if not df.empty else "—",
        df["snap_date"].max() if not df.empty else "—",
    )
    return df


# ---------------------------------------------------------------------------
# Purged & Embargoed Walk-Forward CV
# ---------------------------------------------------------------------------


def _purged_folds(
    df: pd.DataFrame,
    n_folds: int,
) -> list[tuple[npt.NDArray[Any], npt.NDArray[Any]]]:
    dates = np.sort(df["snap_date"].unique())
    n = len(dates)
    fold_size = n // (n_folds + 1)
    folds: list[tuple[npt.NDArray[Any], npt.NDArray[Any]]] = []
    for fi in range(n_folds):
        test_start = dates[(fi + 1) * fold_size]
        test_end = dates[min((fi + 2) * fold_size - 1, n - 1)]
        cutoff = pd.Timestamp(test_start) - pd.Timedelta(days=EMBARGO_DAYS)
        train_mask = df["snap_date"] < cutoff.date()
        test_mask = (df["snap_date"] >= test_start) & (df["snap_date"] <= test_end)
        tr = df.index[train_mask].to_numpy()
        te = df.index[test_mask].to_numpy()
        if len(tr) >= 100 and len(te) >= 20:
            folds.append((tr, te))
    return folds


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def _lgb_params() -> dict[str, Any]:
    return {
        "objective": "binary",
        "n_estimators": 400,
        "learning_rate": 0.03,
        "num_leaves": 31,
        "min_child_samples": 30,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "verbose": -1,
        "random_state": 42,
    }


def _precision_recall_f1(
    y_true: npt.NDArray[Any], y_pred: npt.NDArray[Any]
) -> tuple[float, float, float]:
    tp = float(np.sum((y_pred == 1) & (y_true == 1)))
    fp = float(np.sum((y_pred == 1) & (y_true != 1)))
    fn = float(np.sum((y_pred != 1) & (y_true == 1)))
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


# ---------------------------------------------------------------------------
# Risiko-Metriken
# ---------------------------------------------------------------------------


def _sharpe(period_returns: npt.NDArray[Any], periods_per_year: float = 12.0) -> float:
    """Sharpe Ratio (Risk-Free = 0, monatliche Periodenrenditen × sqrt(12))."""
    if len(period_returns) < 2:
        return 0.0
    std = float(np.std(period_returns, ddof=1))
    if std < 1e-9:
        return 0.0
    return float(np.mean(period_returns) / std * np.sqrt(periods_per_year))


def _max_drawdown(equity: npt.NDArray[Any]) -> float:
    """Maximaler Peak-to-Trough-Drawdown der Equity-Kurve."""
    if len(equity) < 2:
        return 0.0
    peaks = np.maximum.accumulate(equity)
    dd = (equity - peaks) / peaks
    return float(dd.min())


def _calmar(period_returns: npt.NDArray[Any], periods_per_year: float = 12.0) -> float:
    """Calmar Ratio = Annualisierter Return / |MaxDD|."""
    equity = np.cumprod(1 + period_returns)
    mdd = abs(_max_drawdown(equity))
    ann_return = float((1 + np.mean(period_returns)) ** periods_per_year - 1)
    return ann_return / mdd if mdd > 1e-6 else 0.0


def _equity_curve(period_returns: npt.NDArray[Any]) -> npt.NDArray[Any]:
    return np.cumprod(1 + period_returns)


# ---------------------------------------------------------------------------
# Portfolio-Equity-Simulation (monatliches Rebalancing)
# ---------------------------------------------------------------------------


def _monthly_portfolio_returns(
    df: pd.DataFrame,
    strategy: str = "model",
) -> tuple[npt.NDArray[Any], list[date]]:
    """
    Baut monatliche Portfolio-Rendite-Serie aus täglichen Signal-Predictions.

    Monatliches Rebalancing: Für jeden Kalendermonat wird das erste Signal
    je Coin verwendet. Portfoliorendite = Mittel aller aktiven Positionen.

    strategy:
      "model"    — Signal aus Spalte "signal" (model-predicted)
      "bah"      — immer Long (kein Signal, kein Rebalancing-Cost)
      "momentum" — Long wenn return_30d > 0
    """
    df = df.copy()
    df["snap_month"] = pd.to_datetime(df["snap_date"]).dt.to_period("M")

    # Erste Beobachtung je Monat und Coin (PIT-korrekt)
    monthly = df.sort_values("snap_date").groupby(["snap_month", "ticker"]).first().reset_index()

    def _row_return(row: Any) -> float:
        fwd = float(row["fwd_return"])
        if strategy == "model":
            sig = int(row["signal"])
            return (fwd - TRANSACTION_COST_RT) if sig == 1 else 0.0
        elif strategy == "bah":
            return fwd
        else:  # momentum
            sig = int(row["return_30d"] > 0)
            return (fwd - TRANSACTION_COST_RT) if sig == 1 else 0.0

    monthly["strat_return"] = monthly.apply(_row_return, axis=1)
    monthly_port = monthly.groupby("snap_month")["strat_return"].mean()
    months = [pd.Period(p).start_time.date() for p in monthly_port.index]
    return monthly_port.to_numpy(dtype=np.float64), months


# ---------------------------------------------------------------------------
# Walk-Forward: Training + Prediction für alle Folds
# ---------------------------------------------------------------------------


def run_walk_forward(
    df: pd.DataFrame,
    n_folds: int = 5,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """
    Führt Purged Walk-Forward CV durch.
    Gibt zurück:
      - fold_stats: pro Fold Metriken
      - df_oos: OOS-Predictions mit allen Spalten + 'signal', 'proba'
    """
    feat_cols = list(FEATURE_COLS)
    X = df[feat_cols].to_numpy(dtype=np.float32)
    y = df["target_dir"].to_numpy(dtype=np.int32)

    folds = _purged_folds(df, n_folds=n_folds)
    log.info("Walk-Forward CV: %d Folds (Embargo=%d Tage, H=%d)", len(folds), EMBARGO_DAYS, HORIZON)

    up_rate = float(y.mean())
    log.info(
        "Up-Rate gesamt: %.1f%% (>%d%% in %dd)",
        up_rate * 100,
        int(DIRECTIONAL_THRESHOLD * 100),
        HORIZON,
    )

    fold_stats: list[dict[str, Any]] = []
    oos_parts: list[pd.DataFrame] = []

    for fi, (tr_idx, te_idx) in enumerate(folds):
        X_tr, y_tr = X[tr_idx], y[tr_idx]
        X_te, y_te = X[te_idx], y[te_idx]

        model = lgb.LGBMClassifier(**_lgb_params())
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)[:, 1]
        y_pred = (proba >= 0.5).astype(int)

        prec, rec, f1 = _precision_recall_f1(y_te, y_pred)
        acc = float(np.mean(y_te == y_pred))

        # Baselines
        bl_majority = int(y_tr.mean() >= 0.5)
        _, _, f1_maj = _precision_recall_f1(y_te, np.full_like(y_te, bl_majority))
        bl_mom = (df.loc[te_idx, "return_30d"].to_numpy() > 0).astype(int)
        _, _, f1_mom = _precision_recall_f1(y_te, bl_mom)

        # OOS-DataFrame dieses Folds
        fold_df = df.loc[te_idx].copy()
        fold_df["signal"] = y_pred
        fold_df["proba"] = proba
        fold_df["fold"] = fi + 1
        oos_parts.append(fold_df)

        log.info(
            "  Fold %d | F1=%.3f (Maj=%.3f, Mom=%.3f) | Acc=%.3f | n=%d | up%%=%.1f | %s→%s",
            fi + 1,
            f1,
            f1_maj,
            f1_mom,
            acc,
            len(y_te),
            y_te.mean() * 100,
            df.loc[te_idx, "snap_date"].min(),
            df.loc[te_idx, "snap_date"].max(),
        )

        fold_stats.append(
            {
                "fold": fi + 1,
                "n_test": len(y_te),
                "up_rate": float(y_te.mean()),
                "f1": f1,
                "prec": prec,
                "rec": rec,
                "acc": acc,
                "f1_majority": f1_maj,
                "f1_momentum": f1_mom,
                "date_from": str(df.loc[te_idx, "snap_date"].min()),
                "date_to": str(df.loc[te_idx, "snap_date"].max()),
            }
        )

    # Final-Modell auf allen Daten
    log.info("Final-Training auf %d Samples …", len(df))
    final_model = lgb.LGBMClassifier(**_lgb_params())
    final_model.fit(X, y)

    df_oos = pd.concat(oos_parts).sort_values("snap_date").reset_index(drop=True)
    return {
        "model": final_model,
        "fold_stats": fold_stats,
        "feature_cols": feat_cols,
        "n_train": len(df),
        "n_folds": len(folds),
        "up_rate": up_rate,
    }, df_oos


# ---------------------------------------------------------------------------
# Risikoadjustierte Vollanalyse
# ---------------------------------------------------------------------------


def compute_risk_metrics(df_oos: pd.DataFrame) -> dict[str, Any]:
    """
    Berechnet Sharpe, MaxDD, Calmar für Modell, BaH und Momentum.
    Monatliches Rebalancing aus täglichen OOS-Predictions.
    """
    strategies = {
        "model": "Modell (Long wenn p≥0.5)",
        "bah": "Buy-and-Hold (alle Coins, gleich gewichtet)",
        "momentum": "Momentum-Only (Long wenn 30d-Return > 0)",
    }
    results: dict[str, dict[str, float]] = {}

    for strat_key in strategies:
        ret_arr, months = _monthly_portfolio_returns(df_oos, strategy=strat_key)
        equity = _equity_curve(ret_arr)
        sh = _sharpe(ret_arr, periods_per_year=12.0)
        mdd = _max_drawdown(equity)
        cal = _calmar(ret_arr, periods_per_year=12.0)
        ann_ret = float((1 + np.mean(ret_arr)) ** 12 - 1)
        net_mean = float(np.mean(ret_arr))
        signal_rate = 0.0
        if strat_key == "model":
            signal_rate = float(df_oos["signal"].mean())

        results[strat_key] = {
            "sharpe": sh,
            "max_drawdown": mdd,
            "calmar": cal,
            "ann_return": ann_ret,
            "monthly_mean": net_mean,
            "monthly_std": float(np.std(ret_arr, ddof=1)),
            "signal_rate": signal_rate,
            "n_months": len(ret_arr),
        }
        log.info(
            "  [%s] Sharpe=%.2f | MaxDD=%.1f%% | Ann=%.1f%% | Signal-Rate=%.1f%%",
            strat_key,
            sh,
            mdd * 100,
            ann_ret * 100,
            signal_rate * 100,
        )

    # Bear-Market-2022 Subperiode
    bear = df_oos[
        (df_oos["snap_date"] >= BEAR_MARKET_START) & (df_oos["snap_date"] <= BEAR_MARKET_END)
    ]
    bear_results: dict[str, dict[str, float]] = {}
    if not bear.empty:
        for strat_key in strategies:
            ret_arr_b, _ = _monthly_portfolio_returns(bear, strategy=strat_key)
            equity_b = _equity_curve(ret_arr_b)
            bear_results[strat_key] = {
                "max_drawdown": _max_drawdown(equity_b),
                "total_return": float(equity_b[-1] - 1) if len(equity_b) > 0 else 0.0,
                "n_months": len(ret_arr_b),
            }
        log.info(
            "  Bear 2022 | Modell MaxDD=%.1f%% | BaH MaxDD=%.1f%%",
            bear_results["model"]["max_drawdown"] * 100,
            bear_results["bah"]["max_drawdown"] * 100,
        )

    return {"full": results, "bear_2022": bear_results, "strategies": strategies}


# ---------------------------------------------------------------------------
# ml_eval_crypto_v2.md
# ---------------------------------------------------------------------------


def write_eval_v2(
    df: pd.DataFrame,
    result: dict[str, Any],
    df_oos: pd.DataFrame,
    risk: dict[str, Any],
    run_date: str,
) -> None:
    fold_stats = result["fold_stats"]
    strategies = risk["strategies"]
    full = risk["full"]
    bear = risk["bear_2022"]

    def _ms(vals: list[float]) -> str:
        return f"{np.mean(vals):.3f} ± {np.std(vals):.3f}" if vals else "—"

    # Feature importances
    fi_model = result["model"]
    fi_vals = fi_model.feature_importances_
    fi_df = pd.DataFrame({"feature": result["feature_cols"], "imp": fi_vals})
    fi_df = fi_df.sort_values("imp", ascending=False)

    mvrv_coins_str = ", ".join(MVRV_COINS.keys())

    lines: list[str] = [
        "# ML Evaluation Krypto v2 — Risikoadjustiert (PRISMA V3)",
        f"\n**Trainiert:** {run_date}  ",
        f"**Coins:** {', '.join(COINS)}  ",
        f"**Horizont:** H={HORIZON} Tage  ",
        "**Snapshots:** täglich  ",
        f"**N Samples:** {result['n_train']:,}  ",
        f"**N Samples OOS:** {len(df_oos):,}  ",
        f"**CV:** Purged & Embargoed Walk-Forward, {result['n_folds']} Folds, Embargo={EMBARGO_DAYS} Tage  ",
        f"**Up-Rate gesamt:** {result['up_rate'] * 100:.1f}% (30d-Return > 2%)  ",
        f"**MVRV:** Coin Metrics Community API ({mvrv_coins_str})  ",
        f"**Transaktionskosten:** {TRANSACTION_COST_RT * 100:.1f}% Round-Trip  ",
        "\n---\n",
        "## 1 · Risikoadjustierte Kennzahlen (OOS, monatliches Rebalancing)\n",
        "| Strategie | Sharpe | Ann. Return (netto) | Max-Drawdown | Calmar | Signal-Rate |",
        "|-----------|--------|--------------------|--------------|----|-------------|",
    ]

    for k, label in strategies.items():
        m = full[k]
        lines.append(
            f"| {label} | **{m['sharpe']:.2f}** | {m['ann_return'] * 100:.1f}% | "
            f"{m['max_drawdown'] * 100:.1f}% | {m['calmar']:.2f} | "
            f"{m['signal_rate'] * 100:.1f}% |"
        )

    # Vergleich Modell vs BaH
    model_beats_bah_sharpe = full["model"]["sharpe"] > full["bah"]["sharpe"]
    model_beats_mom_sharpe = full["model"]["sharpe"] > full["momentum"]["sharpe"]
    model_less_dd_bah = full["model"]["max_drawdown"] > full["bah"]["max_drawdown"]

    lines += [
        f"\n**Modell Sharpe > BaH Sharpe:** {'✅ JA' if model_beats_bah_sharpe else '❌ NEIN'}  ",
        f"**Modell Sharpe > Momentum Sharpe:** {'✅ JA' if model_beats_mom_sharpe else '❌ NEIN'}  ",
        f"**Modell MaxDD kleiner als BaH MaxDD:** {'✅ JA — Drawdown-Schutz vorhanden' if model_less_dd_bah else '❌ NEIN — kein signifikanter Drawdown-Schutz'}  ",
        "\n---\n",
        "## 2 · Bear-Market 2022 (LUNA + FTX — Jan bis Dez 2022)\n",
    ]

    if bear:
        lines += [
            "| Strategie | MaxDD 2022 | Gesamt-Return 2022 | Monate |",
            "|-----------|------------|-------------------|--------|",
        ]
        for k, label in strategies.items():
            if k in bear:
                b = bear[k]
                lines.append(
                    f"| {label} | {b['max_drawdown'] * 100:.1f}% | "
                    f"{b['total_return'] * 100:.1f}% | {b['n_months']} |"
                )
        if "model" in bear and "bah" in bear:
            model_dd_2022 = bear["model"]["max_drawdown"]
            bah_dd_2022 = bear["bah"]["max_drawdown"]
            lines.append(
                f"\n**Modell-Drawdown 2022 vs BaH-Drawdown 2022:** "
                f"{model_dd_2022 * 100:.1f}% vs {bah_dd_2022 * 100:.1f}% "
                f"→ {'✅ Modell schützt in Bärphasen' if model_dd_2022 > bah_dd_2022 else '❌ Kein Schutz'}"
            )
    else:
        lines.append("*2022 liegt ausserhalb der OOS-Periode (zu wenig Trainingsdaten)*\n")

    lines += [
        "\n---\n",
        "## 3 · Klassifikations-Metriken (CV je Fold)\n",
        "| Fold | F1 | F1-Majority | F1-Momentum | Acc | up% | Periode |",
        "|------|-----|------------|-------------|-----|-----|---------|",
    ]
    for r in fold_stats:
        lines.append(
            f"| {r['fold']} | {r['f1']:.3f} | {r['f1_majority']:.3f} | "
            f"{r['f1_momentum']:.3f} | {r['acc']:.3f} | {r['up_rate'] * 100:.1f}% | "
            f"{r['date_from']}–{r['date_to']} |"
        )

    f1_list = [r["f1"] for r in fold_stats]
    f1_maj = [r["f1_majority"] for r in fold_stats]
    f1_mom = [r["f1_momentum"] for r in fold_stats]
    beats_maj = np.mean(f1_list) > np.mean(f1_maj)
    beats_mom = np.mean(f1_list) > np.mean(f1_mom)
    lines += [
        f"\n**Mittel F1:** {_ms(f1_list)}  ",
        f"**Schlägt Mehrheitsklasse (F1):** {'✅' if beats_maj else '❌'}  ",
        f"**Schlägt Momentum-Only (F1):** {'✅' if beats_mom else '❌'}  ",
        "\n---\n",
        "## 4 · Edge-Stabilität über Folds\n",
        "| Metrik | Mittel | Std | Min | Max |",
        "|--------|--------|-----|-----|-----|",
    ]
    for metric, vals in [
        ("F1", f1_list),
        ("F1-Majority", f1_maj),
        ("F1-Momentum", f1_mom),
    ]:
        lines.append(
            f"| {metric} | {np.mean(vals):.3f} | {np.std(vals):.3f} | "
            f"{np.min(vals):.3f} | {np.max(vals):.3f} |"
        )

    lines += [
        "\n---\n",
        "## 5 · Feature-Importances (Gain, Final-Modell)\n",
        "| Rang | Feature | Importance | Quelle |",
        "|------|---------|-----------|--------|",
    ]
    src_map = {
        "return_1d": "Kurs DB",
        "return_7d": "Kurs DB",
        "return_30d": "Kurs DB",
        "return_90d": "Kurs DB",
        "vol_7d": "Kurs DB",
        "vol_30d": "Kurs DB",
        "rsi_14": "Kurs DB",
        "bb_position": "Kurs DB",
        "macd_hist": "Kurs DB",
        "drawdown_90d": "Kurs DB",
        "fear_greed": "alternative.me",
        "excess_vs_btc_30d": "Kurs DB",
        "mvrv": "Coin Metrics",
    }
    for i, (_, row) in enumerate(fi_df.iterrows()):
        lines.append(
            f"| {i + 1} | `{row['feature']}` | {row['imp']:.1f} | "
            f"{src_map.get(row['feature'], '—')} |"
        )

    lines += [
        "\n---\n",
        "## 6 · Per-Coin-Statistik\n",
        "| Coin | N (OOS) | Up-Rate | Ø 30d-Return | Std | MVRV verfügbar? |",
        "|------|---------|---------|-------------|-----|----------------|",
    ]
    for coin in df_oos["ticker"].unique():
        sub = df_oos[df_oos["ticker"] == coin]
        up = sub["target_dir"].mean()
        ret_m = sub["fwd_return"].mean()
        ret_s = sub["fwd_return"].std()
        has_mvrv = "✅" if coin in MVRV_COINS else "—"
        lines.append(
            f"| {coin} | {len(sub)} | {up * 100:.1f}% | "
            f"{ret_m * 100:.2f}% | {ret_s * 100:.2f}% | {has_mvrv} |"
        )

    lines += [
        "\n---\n",
        "## 7 · Methodologie & Einschränkungen\n",
        f"- **Purged & Embargoed Walk-Forward CV** (López de Prado, Kap. 16), Embargo={EMBARGO_DAYS}d",
        f"- Tägliche Snapshots, H={HORIZON}d Horizont → überlappende Targets im Train (CV-Embargo behebt das)",
        "- Monatliches Rebalancing für Equity-Kurve (überlappungsfreie Periodenrenditen)",
        "- Transaktionskosten: 0.15% Taker + 0.05% Slippage = 0.30% Round-Trip (Binance-Niveau)",
        "- MVRV: Coin Metrics Community API, nur BTC/ETH; andere Coins: Fallback 0.0",
        "- Fear & Greed: alternative.me, täglich ab 2020; vor 2020: Fallback 50 (Neutral)",
        "- Kein MVRV für SOL/ADA/BNB/XRP (kein Free-Tier-Datensatz verfügbar)",
        "- KEIN Deployment, KEIN Live-Betrieb",
        "\n## 8 · Gesamtbewertung\n",
    ]

    model_sh = full["model"]["sharpe"]
    bah_sh = full["bah"]["sharpe"]
    model_mdd = full["model"]["max_drawdown"]
    bah_mdd = full["bah"]["max_drawdown"]

    if model_beats_bah_sharpe and model_less_dd_bah:
        verdict = (
            f"✅ **Risikoadjustierter Edge vorhanden:** Modell Sharpe ({model_sh:.2f}) > "
            f"BaH Sharpe ({bah_sh:.2f}) bei kleinerem MaxDD ({model_mdd * 100:.1f}% vs {bah_mdd * 100:.1f}%)."
        )
    elif model_less_dd_bah and not model_beats_bah_sharpe:
        verdict = (
            f"⚠️ **Teilweise Edge:** Modell reduziert Drawdown ({model_mdd * 100:.1f}% vs {bah_mdd * 100:.1f}%), "
            f"aber Sharpe ({model_sh:.2f}) bleibt unter BaH ({bah_sh:.2f}) — niedrige Signal-Rate kostet Return."
        )
    else:
        verdict = (
            f"❌ **Kein risikoadjustierter Edge:** Modell Sharpe ({model_sh:.2f}) < "
            f"BaH Sharpe ({bah_sh:.2f}), MaxDD ({model_mdd * 100:.1f}%) nicht besser als BaH ({bah_mdd * 100:.1f}%). "
            "Technische Features + Fear&Greed + MVRV reichen für systematischen Edge nicht aus — "
            "Krypto-Kursreihen werden von Regime-Shifts (Bullen-/Bärenmarkt) dominiert, "
            "die kurzfristige Technische Signale überlagern."
        )
    lines.append(verdict)

    out = DOCS_DIR / "ml_eval_crypto_v2.md"
    out.write_text("\n".join(lines))
    log.info("ml_eval_crypto_v2.md geschrieben: %s", out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    log.info("=== Krypto ML v2: H=%d, täglich, Embargo=%d ===", HORIZON, EMBARGO_DAYS)
    df = await build_dataset_crypto_v2()
    if df.empty:
        log.error("Leeres Dataset — Abbruch")
        sys.exit(1)

    df = df.dropna(subset=list(FEATURE_COLS) + ["target_dir"]).reset_index(drop=True)

    result, df_oos = run_walk_forward(df, n_folds=args.folds)

    log.info("Risikoadjustierte Kennzahlen …")
    risk = compute_risk_metrics(df_oos)

    run_date = datetime.now().strftime("%Y-%m-%d")
    path = MODELS_DIR / f"crypto_v2_dir_{run_date}.joblib"
    joblib.dump(result["model"], path)
    log.info("Modell gespeichert: %s", path)

    registry_path = MODELS_DIR / "registry.json"
    reg: dict[str, Any] = (
        json.loads(registry_path.read_text())
        if registry_path.exists()
        else {"active": None, "versions": []}
    )
    reg["active_crypto_v2"] = f"crypto_v2_dir_{run_date}.joblib"
    registry_path.write_text(json.dumps(reg, indent=2))

    write_eval_v2(df, result, df_oos, risk, run_date)
    log.info("Fertig — docs/ml_eval_crypto_v2.md")


if __name__ == "__main__":
    asyncio.run(main())
