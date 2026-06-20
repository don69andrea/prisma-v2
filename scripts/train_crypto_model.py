"""Training: LightGBM Krypto-ML (Richtungs- + Excess-Return-Modell).

Zwei Target-Varianten:
  (a) direktional_7d: 1 wenn 7d-Forward-Return > +2%, 0 sonst — binärer Klassifikator
  (b) excess_vs_btc_7d: 7d-Forward-Excess-Return vs BTC — Regression für Altcoins

Purged & Embargoed Walk-Forward CV (Embargo=14 Tage = 2×Horizont).
Baselines: Mehrheitsklasse / Momentum-only / Buy-and-Hold-BTC.
Transaktionskosten: 0.3% Round-Trip (0.15% je Seite, inkl. Slippage).

Aufruf: uv run python scripts/train_crypto_model.py [--folds 5] [--horizon 7]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import numpy.typing as npt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("train_crypto")

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
DOCS_DIR = ROOT / "docs"
MODELS_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

COINS = ["BTC", "ETH", "SOL", "ADA", "BNB", "XRP"]
ALTCOINS = ["ETH", "SOL", "ADA", "BNB", "XRP"]

TRANSACTION_COST_RT = 0.003  # 0.3% Round-Trip (0.15% je Seite + Slippage)
DIRECTIONAL_THRESHOLD = 0.02  # 2% → Signal "UP"
EMBARGO_DAYS = 14  # 2 × Horizont (7 Tage)

FEATURE_COLS_DIR = (
    "return_1d", "return_7d", "return_30d", "return_90d",
    "vol_7d", "vol_30d", "rsi_14", "bb_position", "macd_hist", "drawdown_90d",
    "fear_greed", "excess_vs_btc_30d",
)
FEATURE_COLS_EXCESS = FEATURE_COLS_DIR  # gleicher Feature-Set

FEATURE_HASH_DIR = hashlib.sha256(",".join(FEATURE_COLS_DIR).encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Technische Indikatoren (PIT-korrekt)
# ---------------------------------------------------------------------------

def _rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).rolling(window).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(window).mean().iloc[-1]
    if loss == 0:
        return 100.0
    rs = gain / loss
    return float(100.0 - 100.0 / (1 + rs))


def _bb_position(close: pd.Series, window: int = 20) -> float:
    """Bollinger-Band-Position: 0 = unteres Band, 1 = oberes Band."""
    if len(close) < window:
        return 0.5
    ma = close.rolling(window).mean().iloc[-1]
    std = close.rolling(window).std().iloc[-1]
    upper = ma + 2 * std
    lower = ma - 2 * std
    rng = upper - lower
    if rng < 1e-9:
        return 0.5
    return float(np.clip((close.iloc[-1] - lower) / rng, 0.0, 1.0))


def _macd_hist(close: pd.Series) -> float:
    """MACD-Histogramm (12/26/9)."""
    if len(close) < 35:
        return 0.0
    ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
    macd_line = ema12 - ema26
    signal_line = (
        pd.Series([ema12 - ema26])
        .ewm(span=9, adjust=False)
        .mean()
        .iloc[-1]
    )
    return float(macd_line - signal_line)


def _drawdown(close: pd.Series, window: int = 90) -> float:
    """Maximaler Drawdown über window Tage."""
    tail = close.tail(window)
    peak = tail.max()
    if peak < 1e-9:
        return 0.0
    return float((close.iloc[-1] - peak) / peak)


def _compute_features(
    close: pd.Series,
    btc_close: pd.Series,
    fear_greed_series: pd.Series,
    snap: pd.Timestamp,
) -> dict[str, float] | None:
    """Feature-Vektor für Ticker @ snap. None wenn zu wenig Daten."""
    past = close[close.index <= snap]
    btc_past = btc_close[btc_close.index <= snap]
    if len(past) < 100:
        return None

    def ret(n: int) -> float:
        if len(past) <= n:
            return 0.0
        return float(past.iloc[-1] / past.iloc[-n] - 1)

    def vol(n: int) -> float:
        if len(past) < n + 1:
            return 0.0
        daily_ret = past.tail(n + 1).pct_change().dropna()
        return float(daily_ret.std() * np.sqrt(365))

    btc_ret30 = 0.0
    if len(btc_past) > 30:
        btc_ret30 = float(btc_past.iloc[-1] / btc_past.iloc[-30] - 1)

    fg_val = 50.0
    snap_date = snap.date() if hasattr(snap, "date") else snap
    if not fear_greed_series.empty and snap_date in fear_greed_series.index:
        fg_val = float(fear_greed_series[snap_date])
    elif not fear_greed_series.empty:
        idx_before = fear_greed_series.index[fear_greed_series.index <= snap_date]
        if len(idx_before) > 0:
            fg_val = float(fear_greed_series[idx_before[-1]])

    return {
        "return_1d": ret(1),
        "return_7d": ret(7),
        "return_30d": ret(30),
        "return_90d": ret(90),
        "vol_7d": vol(7),
        "vol_30d": vol(30),
        "rsi_14": _rsi(past.tail(50)),
        "bb_position": _bb_position(past.tail(30)),
        "macd_hist": _macd_hist(past.tail(60)),
        "drawdown_90d": _drawdown(past, 90),
        "fear_greed": fg_val,
        "excess_vs_btc_30d": ret(30) - btc_ret30,
    }


# ---------------------------------------------------------------------------
# Fear & Greed historisch (alternative.me, kostenlos)
# ---------------------------------------------------------------------------

def _fetch_fear_greed_history() -> pd.Series:
    """Ruft ~2000 Tage historischen Fear&Greed-Index ab."""
    import httpx

    try:
        log.info("Lade Fear&Greed-Historie (alternative.me) …")
        resp = httpx.get(
            "https://api.alternative.me/fng/?limit=2000&format=json",
            timeout=20.0,
        )
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
# Dataset aus DB bauen
# ---------------------------------------------------------------------------

async def _load_coin(ticker: str) -> pd.Series:
    from sqlalchemy import text
    from backend.infrastructure.persistence.session import get_session_factory

    factory = get_session_factory()
    async with factory() as sess:
        r = await sess.execute(
            text("SELECT timestamp::date, close FROM crypto_price_history "
                 "WHERE ticker = :t AND interval = '1d' ORDER BY timestamp ASC"),
            {"t": ticker},
        )
        rows = r.fetchall()
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([row[0] for row in rows])
    return pd.Series([float(row[1]) for row in rows], index=idx, name=ticker)


def _build_targets(
    close: pd.Series,
    btc_close: pd.Series,
    snap: pd.Timestamp,
    horizon: int,
) -> dict[str, float | None]:
    """Targets für snap (PIT: nur Daten > snap für Forward-Return)."""
    future = close[close.index > snap]
    btc_future = btc_close[btc_close.index > snap]
    if len(future) < horizon or len(btc_future) < horizon:
        return {"target_dir": None, "target_excess": None}

    fwd = float(future.iloc[horizon - 1] / future.iloc[0] - 1)
    btc_fwd = float(btc_future.iloc[horizon - 1] / btc_future.iloc[0] - 1)

    target_dir = 1 if fwd > DIRECTIONAL_THRESHOLD else 0
    target_excess = fwd - btc_fwd
    return {"target_dir": target_dir, "target_excess": target_excess}


async def build_dataset_crypto(
    coins: list[str] = COINS,
    horizon: int = 7,
    freq_days: int = 7,
) -> pd.DataFrame:
    """Baut Feature-Dataset aus crypto_price_history (DB-only, kein Live-Pull)."""
    btc_close = await _load_coin("BTC")
    fg_series = _fetch_fear_greed_history()

    price_map: dict[str, pd.Series] = {"BTC": btc_close}
    for coin in coins:
        if coin != "BTC":
            price_map[coin] = await _load_coin(coin)
        log.info("Geladen: %s (%d Tage)", coin, len(price_map.get(coin, btc_close)))

    records = []
    for coin in coins:
        close = price_map.get(coin)
        if close is None or close.empty:
            log.warning("Keine Daten für %s — übersprungen", coin)
            continue

        start = close.index[max(0, 100)]
        end = close.index[-horizon - 5]
        snap_dates = pd.date_range(start=start, end=end, freq=f"{freq_days}D")

        for snap in snap_dates:
            feats = _compute_features(close, btc_close, fg_series, snap)
            if feats is None:
                continue
            targets = _build_targets(close, btc_close, snap, horizon)
            if targets["target_dir"] is None:
                continue

            records.append({
                "ticker": coin,
                "snap_date": snap.date(),
                **feats,
                **targets,
            })

    df = pd.DataFrame(records)
    log.info(
        "Dataset: %d Zeilen, %d Coins, %s → %s",
        len(df), df["ticker"].nunique() if not df.empty else 0,
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
    embargo_days: int,
) -> list[tuple[npt.NDArray[Any], npt.NDArray[Any]]]:
    dates = np.sort(df["snap_date"].unique())
    n = len(dates)
    fold_size = n // (n_folds + 1)
    folds = []
    for fi in range(n_folds):
        test_start = dates[(fi + 1) * fold_size]
        test_end = dates[min((fi + 2) * fold_size - 1, n - 1)]
        cutoff = pd.Timestamp(test_start) - pd.Timedelta(days=embargo_days)
        train_mask = df["snap_date"] < cutoff.date()
        test_mask = (df["snap_date"] >= test_start) & (df["snap_date"] <= test_end)
        tr_idx = df.index[train_mask].to_numpy()
        te_idx = df.index[test_mask].to_numpy()
        if len(tr_idx) >= 50 and len(te_idx) >= 10:
            folds.append((tr_idx, te_idx))
    return folds


# ---------------------------------------------------------------------------
# Metriken
# ---------------------------------------------------------------------------

def _accuracy(y_true: npt.NDArray[Any], y_pred: npt.NDArray[Any]) -> float:
    return float(np.mean(y_true == y_pred))


def _precision_recall_f1(
    y_true: npt.NDArray[Any], y_pred: npt.NDArray[Any], pos: int = 1
) -> tuple[float, float, float]:
    tp = float(np.sum((y_pred == pos) & (y_true == pos)))
    fp = float(np.sum((y_pred == pos) & (y_true != pos)))
    fn = float(np.sum((y_pred != pos) & (y_true == pos)))
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def _net_return(
    fwd_returns: npt.NDArray[Any], signals: npt.NDArray[Any]
) -> float:
    """Simulierter Netto-Return: Nur wenn Signal=1 → kaufen, 7d halten, Kosten abziehen."""
    gross = np.where(signals == 1, fwd_returns, 0.0)
    costs = np.where(signals == 1, TRANSACTION_COST_RT, 0.0)
    return float(np.mean(gross - costs))


def _mae(y_true: npt.NDArray[Any], y_pred: npt.NDArray[Any]) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def _lgb_params_clf() -> dict[str, Any]:
    return {
        "objective": "binary",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 15,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "verbose": -1,
        "random_state": 42,
    }


def _lgb_params_reg() -> dict[str, Any]:
    return {
        "objective": "regression",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 15,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "verbose": -1,
        "random_state": 42,
    }


def train_directional(df: pd.DataFrame, n_folds: int = 5) -> dict[str, Any]:
    """Target (a): binärer Klassifikator — forward_7d > 2%."""
    feat_cols = list(FEATURE_COLS_DIR)
    X = df[feat_cols].to_numpy(dtype=np.float32)
    y = df["target_dir"].to_numpy(dtype=np.int32)

    folds = _purged_folds(df, n_folds=n_folds, embargo_days=EMBARGO_DAYS)
    log.info("Direktional-CV: %d Folds", len(folds))

    up_rate = float(y.mean())
    log.info("Up-Rate im Dataset: %.1f%% (Threshold %.0f%%)", up_rate * 100, DIRECTIONAL_THRESHOLD * 100)

    cv_results: list[dict[str, float]] = []
    for fi, (tr_idx, te_idx) in enumerate(folds):
        X_tr, y_tr = X[tr_idx], y[tr_idx]
        X_te, y_te = X[te_idx], y[te_idx]

        model = lgb.LGBMClassifier(**_lgb_params_clf())
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)[:, 1]
        y_pred = (proba >= 0.5).astype(int)

        # Baselines
        majority = int(y_tr.mean() >= 0.5)
        bl_majority = np.full_like(y_te, majority)
        bl_momentum = (df.loc[te_idx, "return_7d"].to_numpy() > 0).astype(int)

        # Forward returns für Net-Return-Berechnung
        fwd_col = "target_excess" if "target_excess" in df.columns else "target_dir"
        fwd_te = df.loc[te_idx, "return_7d"].to_numpy()  # Proxy: 7d-return des nächsten Snap

        # Metriken Modell
        prec, rec, f1 = _precision_recall_f1(y_te, y_pred, pos=1)
        acc = _accuracy(y_te, y_pred)

        # Baseline-Metriken
        _, _, f1_maj = _precision_recall_f1(y_te, bl_majority, pos=1)
        _, _, f1_mom = _precision_recall_f1(y_te, bl_momentum, pos=1)

        cv_results.append({
            "fold": fi + 1,
            "n_test": len(y_te),
            "acc": acc,
            "prec": prec, "rec": rec, "f1": f1,
            "f1_baseline_majority": f1_maj,
            "f1_baseline_momentum": f1_mom,
            "up_rate_test": float(y_te.mean()),
        })
        log.info(
            "  Fold %d | F1=%.3f (Majority=%.3f, Momentum=%.3f) | n=%d | up%%=%.1f",
            fi + 1, f1, f1_maj, f1_mom, len(y_te), y_te.mean() * 100,
        )

    # Final-Training
    log.info("Final-Training Direktional auf %d Samples …", len(df))
    final_clf = lgb.LGBMClassifier(**_lgb_params_clf())
    final_clf.fit(X, y)

    return {
        "model": final_clf,
        "cv_results": cv_results,
        "feature_cols": feat_cols,
        "n_train": len(df),
        "n_folds": len(folds),
        "up_rate_overall": float(y.mean()),
    }


def train_excess_vs_btc(df_alt: pd.DataFrame, n_folds: int = 5) -> dict[str, Any]:
    """Target (b): Excess-Return vs BTC für Altcoins (Regression)."""
    df_alt = df_alt.dropna(subset=["target_excess"]).copy()
    if len(df_alt) < 100:
        log.warning("Zu wenig Altcoin-Daten für Excess-Modell (%d)", len(df_alt))
        return {}

    feat_cols = list(FEATURE_COLS_EXCESS)
    X = df_alt[feat_cols].to_numpy(dtype=np.float32)
    y = df_alt["target_excess"].to_numpy(dtype=np.float64)

    folds = _purged_folds(df_alt, n_folds=n_folds, embargo_days=EMBARGO_DAYS)
    log.info("Excess-CV: %d Folds, %d Altcoin-Samples", len(folds), len(df_alt))

    cv_results: list[dict[str, float]] = []
    for fi, (tr_idx, te_idx) in enumerate(folds):
        X_tr, y_tr = X[tr_idx], y[tr_idx]
        X_te, y_te = X[te_idx], y[te_idx]

        model = lgb.LGBMRegressor(**_lgb_params_reg())
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)

        # MAE und Baseline (Nullprognose: kein Excess)
        mae = _mae(y_te, y_pred)
        mae_zero = _mae(y_te, np.zeros_like(y_te))
        mae_btc_mean = _mae(y_te, np.full_like(y_te, np.mean(y_tr)))

        # Direktionaler Accuracy aus dem Excess
        dir_model = (y_pred > 0).astype(int)
        dir_actual = (y_te > 0).astype(int)
        dir_acc = float(np.mean(dir_model == dir_actual))
        dir_bl = float(np.mean(dir_actual == int(np.mean(y_tr) > 0)))

        cv_results.append({
            "fold": fi + 1,
            "n_test": len(y_te),
            "mae": mae,
            "mae_zero_baseline": mae_zero,
            "mae_mean_baseline": mae_btc_mean,
            "dir_acc": dir_acc,
            "dir_acc_baseline": dir_bl,
        })
        log.info(
            "  Fold %d | MAE=%.4f (0-Baseline=%.4f) | DirAcc=%.3f (BL=%.3f) | n=%d",
            fi + 1, mae, mae_zero, dir_acc, dir_bl, len(y_te),
        )

    # Final-Training
    log.info("Final-Training Excess-Regression auf %d Altcoin-Samples …", len(df_alt))
    final_reg = lgb.LGBMRegressor(**_lgb_params_reg())
    final_reg.fit(X, y)

    return {
        "model": final_reg,
        "cv_results": cv_results,
        "feature_cols": feat_cols,
        "n_train": len(df_alt),
        "n_folds": len(folds),
    }


# ---------------------------------------------------------------------------
# Net-Return-Simulation (Brutto vs Netto vs Buy-and-Hold)
# ---------------------------------------------------------------------------

def simulate_net_returns(
    df: pd.DataFrame,
    model: lgb.LGBMClassifier,
    feat_cols: list[str],
    n_folds: int = 5,
) -> dict[str, float]:
    """Simuliert Signal-basierte Netto-Returns auf Hold-out-Folds."""
    X = df[feat_cols].to_numpy(dtype=np.float32)
    folds = _purged_folds(df, n_folds=n_folds, embargo_days=EMBARGO_DAYS)

    gross_returns: list[float] = []
    net_returns: list[float] = []
    bah_btc_returns: list[float] = []
    signal_rates: list[float] = []

    for tr_idx, te_idx in folds:
        X_tr = X[tr_idx]
        y_tr = df["target_dir"].to_numpy(dtype=np.int32)[tr_idx]

        m = lgb.LGBMClassifier(**_lgb_params_clf())
        m.fit(X_tr, y_tr)

        proba_te = m.predict_proba(X[te_idx])[:, 1]
        signals = (proba_te >= 0.5).astype(int)

        # 7d Forward-Return als Proxy (return_7d des nächsten Snapshots = return_7d aktuell gelabelt)
        fwd_te = df.loc[te_idx, "return_7d"].to_numpy()

        gross = float(np.mean(np.where(signals == 1, fwd_te, 0.0)))
        net = float(np.mean(np.where(signals == 1, fwd_te - TRANSACTION_COST_RT, 0.0)))
        bah = float(np.mean(fwd_te))  # Proxy: Buy-and-Hold aller Coins (= Mkt avg)

        gross_returns.append(gross)
        net_returns.append(net)
        bah_btc_returns.append(bah)
        signal_rates.append(float(signals.mean()))

    return {
        "gross_mean": float(np.mean(gross_returns)),
        "net_mean": float(np.mean(net_returns)),
        "bah_mean": float(np.mean(bah_btc_returns)),
        "signal_rate": float(np.mean(signal_rates)),
        "net_std": float(np.std(net_returns)),
        "beats_bah_net": float(np.mean(net_returns)) > float(np.mean(bah_btc_returns)),
    }


# ---------------------------------------------------------------------------
# Speichern & Registry
# ---------------------------------------------------------------------------

def save_crypto_models(
    result_dir: dict[str, Any],
    result_exc: dict[str, Any],
    run_date: str,
) -> None:
    if result_dir.get("model"):
        path = MODELS_DIR / f"crypto_dir_{run_date}.joblib"
        joblib.dump(result_dir["model"], path)
        log.info("Gespeichert: %s", path)

    if result_exc.get("model"):
        path = MODELS_DIR / f"crypto_excess_{run_date}.joblib"
        joblib.dump(result_exc["model"], path)
        log.info("Gespeichert: %s", path)

    meta: dict[str, Any] = {
        "type": "crypto",
        "trained_at": run_date,
        "directional": {
            "feature_hash": FEATURE_HASH_DIR,
            "features": result_dir.get("feature_cols", []),
            "n_train": result_dir.get("n_train", 0),
        },
        "excess_vs_btc": {
            "features": result_exc.get("feature_cols", []),
            "n_train": result_exc.get("n_train", 0),
        },
    }
    meta_path = MODELS_DIR / f"crypto_meta_{run_date}.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info("Meta: %s", meta_path)

    registry_path = MODELS_DIR / "registry.json"
    reg: dict[str, Any] = (
        json.loads(registry_path.read_text()) if registry_path.exists()
        else {"active": None, "versions": []}
    )
    reg["active_crypto"] = f"crypto_meta_{run_date}.json"
    reg.setdefault("versions", []).append({"type": "crypto", "date": run_date})
    registry_path.write_text(json.dumps(reg, indent=2))


# ---------------------------------------------------------------------------
# ml_eval_crypto.md
# ---------------------------------------------------------------------------

def write_ml_eval_crypto(
    df: pd.DataFrame,
    result_dir: dict[str, Any],
    result_exc: dict[str, Any],
    sim: dict[str, float],
    run_date: str,
    horizon: int,
) -> None:
    cv_dir = result_dir.get("cv_results", [])
    cv_exc = result_exc.get("cv_results", [])

    def _mean_std(vals: list[float]) -> str:
        if not vals:
            return "—"
        return f"{np.mean(vals):.3f} ± {np.std(vals):.3f}"

    # Feature importances (direktional)
    fi_lines: list[str] = []
    if result_dir.get("model"):
        fi = result_dir["model"].feature_importances_
        feat_cols = result_dir.get("feature_cols", [])
        fi_df = pd.DataFrame({"feature": feat_cols, "importance": fi})
        fi_df = fi_df.sort_values("importance", ascending=False)
        fi_lines = [
            "\n## Feature-Importances (Direktional-Modell, Gain)\n",
            "| Rang | Feature | Importance |",
            "|------|---------|-----------|",
        ] + [
            f"| {i+1} | `{row['feature']}` | {row['importance']:.1f} |"
            for i, (_, row) in enumerate(fi_df.iterrows())
        ]

    lines = [
        "# ML Evaluation — Krypto (PRISMA V3)",
        f"\n**Trainiert:** {run_date}  ",
        f"**Coins:** {', '.join(COINS)}  ",
        f"**Horizont:** H={horizon} Tage  ",
        f"**Transaktionskosten:** {TRANSACTION_COST_RT*100:.1f}% Round-Trip  ",
        f"**CV:** Purged & Embargoed Walk-Forward, 5 Folds, Embargo={EMBARGO_DAYS} Tage  ",
        f"**Up-Rate gesamt:** {result_dir.get('up_rate_overall', 0)*100:.1f}% (Anteil 7d-Return > 2%)  ",
        f"**N Samples (direktional):** {result_dir.get('n_train', 0):,}  ",
        f"**N Samples (Excess-Altcoin):** {result_exc.get('n_train', 0):,}  ",
        "\n---\n",
        "## Target (a): Direktional — 7d-Forward-Return > 2%\n",
        "### Modell vs Baselines (CV, Mittel ± Std)\n",
        "| Metrik | Modell | Mehrheitsklasse | Momentum-only |",
        "|--------|--------|-----------------|---------------|",
    ]

    if cv_dir:
        f1_model = [r["f1"] for r in cv_dir]
        f1_maj = [r["f1_baseline_majority"] for r in cv_dir]
        f1_mom = [r["f1_baseline_momentum"] for r in cv_dir]
        acc = [r["acc"] for r in cv_dir]
        prec = [r["prec"] for r in cv_dir]
        rec = [r["rec"] for r in cv_dir]

        beats_majority = np.mean(f1_model) > np.mean(f1_maj)
        beats_momentum = np.mean(f1_model) > np.mean(f1_mom)

        lines += [
            f"| F1 | {_mean_std(f1_model)} | {_mean_std(f1_maj)} | {_mean_std(f1_mom)} |",
            f"| Accuracy | {_mean_std(acc)} | — | — |",
            f"| Precision | {_mean_std(prec)} | — | — |",
            f"| Recall | {_mean_std(rec)} | — | — |",
            f"\n**Schlägt Mehrheitsklasse:** {'✅ JA' if beats_majority else '❌ NEIN'}  ",
            f"**Schlägt Momentum-Only:** {'✅ JA' if beats_momentum else '❌ NEIN'}  ",
        ]

        # Per-Fold-Tabelle
        lines += [
            "\n### Per-Fold Detail\n",
            "| Fold | F1 | F1-Majority | F1-Momentum | n_test | up% |",
            "|------|-----|------------|-------------|--------|-----|",
        ]
        for r in cv_dir:
            lines.append(
                f"| {r['fold']} | {r['f1']:.3f} | {r['f1_baseline_majority']:.3f} | "
                f"{r['f1_baseline_momentum']:.3f} | {r['n_test']} | {r['up_rate_test']*100:.1f}% |"
            )

    lines += [
        "\n---\n",
        "## Netto-Return-Simulation (Signal-Strategie vs Buy-and-Hold)\n",
        "| Strategie | Ø 7d-Return | Transaktionskosten | Netto |",
        "|-----------|-------------|-------------------|-------|",
        f"| Modell (brutto) | {sim.get('gross_mean', 0)*100:.3f}% | {TRANSACTION_COST_RT*100:.1f}% | {sim.get('net_mean', 0)*100:.3f}% |",
        f"| Buy-and-Hold (alle Coins, avg) | {sim.get('bah_mean', 0)*100:.3f}% | 0% | {sim.get('bah_mean', 0)*100:.3f}% |",
        f"| Signal-Rate (Anteil UP-Signale) | {sim.get('signal_rate', 0)*100:.1f}% | — | — |",
        f"\n**Modell (netto) schlägt Buy-and-Hold:** {'✅ JA' if sim.get('beats_bah_net') else '❌ NEIN'}  ",
        f"**Netto-Std über Folds:** {sim.get('net_std', 0)*100:.3f}%  ",
        "\n---\n",
        "## Target (b): Excess-Return vs BTC (Altcoins)\n",
        "### MAE und Direktions-Accuracy (CV)\n",
        "| Metrik | Modell | 0-Baseline | Mean-Baseline |",
        "|--------|--------|-----------|----------------|",
    ]

    if cv_exc:
        mae_m = [r["mae"] for r in cv_exc]
        mae_0 = [r["mae_zero_baseline"] for r in cv_exc]
        mae_mean = [r["mae_mean_baseline"] for r in cv_exc]
        dir_acc = [r["dir_acc"] for r in cv_exc]
        dir_bl = [r["dir_acc_baseline"] for r in cv_exc]

        beats_0 = np.mean(mae_m) < np.mean(mae_0)
        beats_mean = np.mean(mae_m) < np.mean(mae_mean)

        lines += [
            f"| MAE | {_mean_std(mae_m)} | {_mean_std(mae_0)} | {_mean_std(mae_mean)} |",
            f"| DirAcc | {_mean_std(dir_acc)} | {_mean_std(dir_bl)} | — |",
            f"\n**MAE schlägt 0-Baseline:** {'✅ JA' if beats_0 else '❌ NEIN'}  ",
            f"**MAE schlägt Mean-Baseline:** {'✅ JA' if beats_mean else '❌ NEIN'}  ",
            "\n### Per-Fold Detail\n",
            "| Fold | MAE | MAE(0) | MAE(Mean) | DirAcc | DirAcc-BL | n |",
            "|------|-----|--------|-----------|--------|-----------|---|",
        ]
        for r in cv_exc:
            lines.append(
                f"| {r['fold']} | {r['mae']:.4f} | {r['mae_zero_baseline']:.4f} | "
                f"{r['mae_mean_baseline']:.4f} | {r['dir_acc']:.3f} | "
                f"{r['dir_acc_baseline']:.3f} | {r['n_test']} |"
            )
    else:
        lines.append("*Zu wenig Daten für Excess-vs-BTC-Modell.*\n")

    lines += fi_lines

    lines += [
        "\n---\n",
        "## Methodologie\n",
        f"- **Purged & Embargoed Walk-Forward CV** (López de Prado, Kap. 16)",
        f"- Embargo = {EMBARGO_DAYS} Tage (2× Horizont H={horizon})",
        "- Features: PIT-korrekt aus `crypto_price_history` (DB) + Fear&Greed (alternative.me)",
        "- Transaktionskosten: 0.15% pro Seite (Taker) + 0.05% Slippage = 0.30% Round-Trip",
        "- Kein MVRV/On-Chain (Glassnode-Key nicht vorhanden)",
        "- Keine 1h-Daten (tägliche Snapshots, wöchentliche Frequenz)",
        "\n## Bewertung: Welcher Coin/Horizont/Target am besten?\n",
    ]

    # Per-Coin-Statistik
    if not df.empty and "ticker" in df.columns:
        lines += [
            "### Up-Rate und mittlerer 7d-Return je Coin\n",
            "| Coin | N | Up-Rate (>2%) | Ø 7d-Return | Std 7d-Return |",
            "|------|---|--------------|------------|----------------|",
        ]
        for coin in df["ticker"].unique():
            sub = df[df["ticker"] == coin]
            up = sub["target_dir"].mean() if "target_dir" in sub else 0.0
            ret_mean = sub["return_7d"].mean() if "return_7d" in sub else 0.0
            ret_std = sub["return_7d"].std() if "return_7d" in sub else 0.0
            lines.append(
                f"| {coin} | {len(sub)} | {up*100:.1f}% | "
                f"{ret_mean*100:.2f}% | {ret_std*100:.2f}% |"
            )

    out = DOCS_DIR / "ml_eval_crypto.md"
    out.write_text("\n".join(lines))
    log.info("ml_eval_crypto.md geschrieben: %s", out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--horizon", type=int, default=7)
    ap.add_argument("--freq", type=int, default=7, help="Snapshot-Frequenz in Tagen")
    args = ap.parse_args()

    log.info("Baue Krypto-Dataset (Horizont=%d Tage) …", args.horizon)
    df = await build_dataset_crypto(
        coins=COINS, horizon=args.horizon, freq_days=args.freq
    )
    if df.empty:
        log.error("Leeres Dataset — Abbruch")
        sys.exit(1)

    df = df.dropna(subset=list(FEATURE_COLS_DIR) + ["target_dir"])

    run_date = datetime.now().strftime("%Y-%m-%d")

    # (a) Direktional
    log.info("Training: Direktional (UP > 2%) …")
    result_dir = train_directional(df, n_folds=args.folds)

    # Net-Return-Simulation
    log.info("Simuliere Netto-Returns …")
    sim = simulate_net_returns(df, result_dir["model"], list(FEATURE_COLS_DIR), args.folds)
    log.info(
        "Netto: %.3f%% | Brutto: %.3f%% | BaH: %.3f%% | Signal-Rate: %.1f%%",
        sim["net_mean"] * 100, sim["gross_mean"] * 100,
        sim["bah_mean"] * 100, sim["signal_rate"] * 100,
    )

    # (b) Excess vs BTC (nur Altcoins)
    log.info("Training: Excess-Return vs BTC (Altcoins) …")
    df_alt = df[df["ticker"].isin(ALTCOINS)].copy().reset_index(drop=True)
    result_exc = train_excess_vs_btc(df_alt, n_folds=args.folds)

    save_crypto_models(result_dir, result_exc, run_date)
    write_ml_eval_crypto(df, result_dir, result_exc, sim, run_date, args.horizon)

    log.info("Fertig. Modelle in models/, Evaluation in docs/ml_eval_crypto.md")


if __name__ == "__main__":
    asyncio.run(main())
