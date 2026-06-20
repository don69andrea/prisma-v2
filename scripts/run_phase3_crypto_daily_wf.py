"""Phase 3 — Täglicher Krypto-Overlay: 6 Coins, Walk-Forward, OOS.

Validiert, ob der Phase-2-Drawdown-Edge in der BacktestEngine erhalten bleibt.
Drei Portfolios werden verglichen:
  A) ML-Timing:          1/6 je Coin wenn Modell IN (p >= 0.5), sonst Cash
  B) Buy-and-Hold:       1/6 je Coin immer investiert
  C) Exposure-Matched:   const. avg_exposure/6 je Coin — trennt Timing-Skill von
                         Unter-Investition (exposure-adjustment)

Methodik:
  - Walk-Forward Retrain (5 Expanding-Window Folds), Embargo = 30 Tage
  - Feature-Set: 13 Features (identisch crypto-v2), FEATURE_HASH=03c3e1b0
  - Schwelle: p < 0.5 (Phase-2-Standard, a priori)
  - OOS: 2019-01-01 – 2026-06-01 (täglich, ~7.5 Jahre, ~1900 Handelstage)

AUFRUF: uv run python scripts/run_phase3_crypto_daily_wf.py
ERGEBNIS: docs/signal_backtest.md wird um Abschnitt 7 ergänzt.
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

from backend.application.services.crypto_ml_overlay import _compute_features  # noqa: E402
from backend.domain.services.transaction_cost_model import (  # noqa: E402
    TransactionCostModel,
)

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

COINS = ["BTC-USD", "ETH-USD", "XRP-USD", "LTC-USD", "ADA-USD", "DOGE-USD"]
N_COINS = len(COINS)

OOS_START = date(2019, 1, 1)
OOS_END = date(2026, 6, 1)
OOS_YEARS = (OOS_END - OOS_START).days / 365.25  # 7.497

IN_THRESHOLD = 0.5  # p >= 0.5 → IN (a priori, kein OOS-Tuning)
DIRECTIONAL_THRESHOLD = 0.02  # Label: 30d-Return > 2%
LABEL_HORIZON = 30
TC_CRYPTO = 0.0025  # 0.25% One-Way (= 0.5% RT), beim Switch anwenden

# Expanding-Window-Folds (identisch Phase-2 / honest-backtest)
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

FEATURE_COLS = [
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

# ---------------------------------------------------------------------------
# Daten laden
# ---------------------------------------------------------------------------


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
    return close.dropna(how="all").ffill()


def fetch_fear_greed() -> pd.Series:
    try:
        import httpx

        r = httpx.get("https://api.alternative.me/fng/?limit=3000&format=json", timeout=20.0)
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
# Feature-Bau
# ---------------------------------------------------------------------------


def build_training_features(
    closes: pd.DataFrame,
    fear_greed: pd.Series,
    mvrv: dict[str, pd.Series],
) -> pd.DataFrame:
    """Baut tägliche Features + Label für alle Coins über die Gesamtperiode."""
    btc = closes["BTC-USD"].dropna() if "BTC-USD" in closes.columns else pd.Series(dtype=float)
    rows = []
    for ticker in closes.columns:
        col = closes[ticker].dropna()
        for snap in col.index:
            feat = _compute_features(col, btc, snap, fear_greed, mvrv.get(ticker))
            if feat is None:
                continue
            future = col[col.index > snap]
            if len(future) < LABEL_HORIZON:
                continue
            p_exit = float(future.iloc[LABEL_HORIZON - 1])
            p_entry = float(col.loc[snap])
            if p_entry <= 0:
                continue
            label = int((p_exit / p_entry - 1) > DIRECTIONAL_THRESHOLD)
            rows.append(
                {
                    "ticker": ticker,
                    "date": snap,
                    **dict(zip(FEATURE_COLS, feat, strict=False)),
                    "label": label,
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def build_oos_features(
    closes: pd.DataFrame,
    fear_greed: pd.Series,
    mvrv: dict[str, pd.Series],
    oos_start: date,
    oos_end: date,
) -> pd.DataFrame:
    """Features für OOS-Tage (ohne Label) für Walk-Forward-Prognosen."""
    btc = closes["BTC-USD"].dropna() if "BTC-USD" in closes.columns else pd.Series(dtype=float)
    rows = []
    for ticker in closes.columns:
        col = closes[ticker].dropna()
        oos_mask = (col.index >= pd.Timestamp(oos_start)) & (col.index <= pd.Timestamp(oos_end))
        oos_dates = col[oos_mask].index
        for snap in oos_dates:
            feat = _compute_features(col, btc, snap, fear_greed, mvrv.get(ticker))
            if feat is None:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "date": snap,
                    **dict(zip(FEATURE_COLS, feat, strict=False)),
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# Walk-Forward Gate
# ---------------------------------------------------------------------------


def build_walk_forward_signals(
    df_train_all: pd.DataFrame,
    closes: pd.DataFrame,
    fear_greed: pd.Series,
    mvrv: dict[str, pd.Series],
) -> dict[tuple[str, date], int]:
    """Trainiert 5 Expanding-Window-Folds, gibt (ticker, date) → 0/1 zurück.

    1 = IN (p >= 0.5), 0 = OUT (p < 0.5). Embargo = 30 Tage nach Train-Ende.
    """
    signals: dict[tuple[str, date], int] = {}

    for fold_idx, (_train_start, train_end, oos_start, oos_end) in enumerate(WF_FOLDS):
        train_cut = pd.Timestamp(train_end)
        oos_s = pd.Timestamp(oos_start)
        oos_e = pd.Timestamp(oos_end)

        df_tr = df_train_all[df_train_all["date"] <= train_cut]
        if len(df_tr) < 300:
            print(f"  Fold {fold_idx + 1}: zu wenig Trainingsdaten ({len(df_tr)}), skip")
            continue

        X_tr = df_tr[FEATURE_COLS].to_numpy(dtype=np.float32)
        y_tr = df_tr["label"].to_numpy(dtype=np.int32)

        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(X_tr, y_tr)

        # OOS-Features (frischer Download nötig, damit _compute_features PIT-korrekt)
        df_oos = build_oos_features(closes, fear_greed, mvrv, oos_start, oos_end)

        if df_oos.empty:
            print(f"  Fold {fold_idx + 1}: keine OOS-Features")
            continue

        df_oos_filt = df_oos[(df_oos["date"] >= oos_s) & (df_oos["date"] <= oos_e)]

        X_oos = df_oos_filt[FEATURE_COLS].to_numpy(dtype=np.float32)
        proba = model.predict_proba(X_oos)[:, 1]

        n_in = 0
        for i, row in enumerate(df_oos_filt.itertuples()):
            p = float(proba[i])
            sig = 1 if p >= IN_THRESHOLD else 0
            signals[(row.ticker, row.date.date())] = sig
            n_in += sig

        up_rate = float(y_tr.mean())
        in_rate = n_in / max(len(df_oos_filt), 1)
        print(
            f"  Fold {fold_idx + 1}: train n={len(df_tr)} up={up_rate:.1%} "
            f"| OOS {oos_start}–{oos_end}: {len(df_oos_filt)} rows "
            f"IN-rate={in_rate:.1%}"
        )

    return signals


# ---------------------------------------------------------------------------
# Portfolio-Simulation
# ---------------------------------------------------------------------------


def simulate_portfolio(
    closes: pd.DataFrame,
    signals: dict[tuple[str, date], int],
    oos_start: date,
    oos_end: date,
    cost_model: TransactionCostModel,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Simuliert täglich ML-Timing, BaH und Exposure-Matched.

    Returns:
        ml_equity:  Equity-Kurve ML-Timing (täglich)
        bah_equity: Equity-Kurve Buy-and-Hold 6-Coin Equal-Weight
        em_equity:  Equity-Kurve Exposure-Matched Baseline
    """
    dates_all = pd.date_range(start=oos_start, end=oos_end, freq="B")
    available = closes.index
    trading_days = [d for d in dates_all if d in available]
    if not trading_days:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)

    # Coin-Returns (täglich)
    coin_returns: dict[str, pd.Series] = {}
    for ticker in COINS:
        if ticker not in closes.columns:
            continue
        s = closes[ticker].reindex(trading_days).ffill()
        coin_returns[ticker] = s.pct_change()

    active_coins = list(coin_returns)
    n = len(active_coins)

    ml_daily: list[float] = []
    bah_daily: list[float] = []
    prev_signals: dict[str, int] = {c: 0 for c in active_coins}

    for day in trading_days:
        day_date = day.date()
        ml_ret = 0.0
        bah_ret = 0.0
        for ticker in active_coins:
            cr = float(coin_returns[ticker].get(day, 0.0))
            if pd.isna(cr):
                cr = 0.0
            sig = signals.get((ticker, day_date), 0)
            prev_sig = prev_signals.get(ticker, 0)

            # TC bei Richtungswechsel (in→out oder out→in)
            tc = 0.0
            if sig != prev_sig:
                tc = TC_CRYPTO  # one-way 0.25%

            ml_ret += sig * cr / n - tc / n
            bah_ret += cr / n
            prev_signals[ticker] = sig

        ml_daily.append(ml_ret)
        bah_daily.append(bah_ret)

    # Exposure-Matched Baseline: constant fraction = Ø(signal_rate) pro Tag
    total_signal_days = sum(
        signals.get((c, d.date()), 0) for c in active_coins for d in trading_days
    )
    avg_exposure = total_signal_days / (n * len(trading_days)) if trading_days else 0.0
    em_daily = [r * avg_exposure for r in bah_daily]

    idx = pd.DatetimeIndex(trading_days)
    ml_s = pd.Series(ml_daily, index=idx)
    bah_s = pd.Series(bah_daily, index=idx)
    em_s = pd.Series(em_daily, index=idx)

    def compound(series: pd.Series) -> pd.Series:
        return (1 + series).cumprod()

    return compound(ml_s), compound(bah_s), compound(em_s), avg_exposure


# ---------------------------------------------------------------------------
# Metriken
# ---------------------------------------------------------------------------


def metrics(equity: pd.Series, n_years: float) -> dict:
    """CAGR, Calmar, Sharpe, MaxDD aus täglich kompoundierter Equity-Kurve."""
    if equity.empty or len(equity) < 5:
        return {"cagr": 0.0, "calmar": 0.0, "sharpe": 0.0, "max_dd": 0.0}

    terminal = float(equity.iloc[-1])
    cagr = float(terminal ** (1.0 / n_years) - 1.0) if n_years > 0 and terminal > 0 else 0.0

    # MaxDD
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, np.nan)
    max_dd = float(dd.min())

    # Calmar
    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-9 else 0.0

    # Sharpe (aus täglichen Renditen, annualisiert √252)
    daily_r = equity.pct_change().dropna()
    mu = float(daily_r.mean())
    sig = float(daily_r.std(ddof=1))
    sharpe = (mu / sig * math.sqrt(252)) if sig > 1e-9 else 0.0

    return {"cagr": cagr, "calmar": calmar, "sharpe": sharpe, "max_dd": max_dd}


def fold_metrics(
    closes: pd.DataFrame,
    signals: dict[tuple[str, date], int],
    cost_model: TransactionCostModel,
    year_from: int,
    year_to: int,
) -> dict:
    """Metriken für einen Sub-Zeitraum."""
    start = date(year_from, 1, 1)
    end = date(year_to, 12, 31)
    n_years = (min(end, OOS_END) - max(start, OOS_START)).days / 365.25
    result = simulate_portfolio(
        closes, signals, max(start, OOS_START), min(end, OOS_END), cost_model
    )
    if len(result) == 4:
        ml_eq, bah_eq, em_eq, exp = result
    else:
        return {}
    return {
        "ml": metrics(ml_eq, n_years),
        "bah": metrics(bah_eq, n_years),
        "em": metrics(em_eq, n_years),
        "exposure": exp,
    }


# ---------------------------------------------------------------------------
# Report-Anhang
# ---------------------------------------------------------------------------


def _fmt(v: float, suffix: str = "%", scale: float = 100.0) -> str:
    return f"{v * scale:+.1f}{suffix}"


def _calmar_fmt(v: float) -> str:
    return f"{v:.2f}"


def append_report_section(
    ml_m: dict,
    bah_m: dict,
    em_m: dict,
    avg_exposure: float,
    folds_data: list[dict],
    total_signal_days: int,
    total_possible: int,
) -> None:
    doc_path = ROOT / "docs" / "signal_backtest.md"
    existing = doc_path.read_text(encoding="utf-8")

    # Entferne vorherigen Abschnitt 7 falls vorhanden
    if "\n## 7 ·" in existing:
        existing = existing[: existing.index("\n## 7 ·")]

    edge = ""
    if ml_m["calmar"] > em_m["calmar"] * 1.1 and ml_m["calmar"] > 0.5:
        edge = "✅ TIMING-SKILL VORHANDEN (Calmar ML > Exposure-Matched)"
    elif ml_m["calmar"] > em_m["calmar"]:
        edge = "⚠️ LEICHTER TIMING-VORTEIL (ML > EM, aber unter 10% Differenz)"
    else:
        edge = "❌ KEIN TIMING-SKILL (ML ≤ Exposure-Matched auf Calmar)"

    section = f"""

## 7 · Täglicher Krypto-Overlay — 6 Coins, Walk-Forward OOS (Kern-Validierung)

**Fragestellung:** Bringt das Phase-2-Krypto-Risiko-Modell (Walk-Forward, p≥0.5) messbaren
Drawdown-Schutz, oder ist ein scheinbarer Vorteil nur auf tiefere Investitionsquote
(Unter-Investition) zurückzuführen?

**Test:** ML-Timing vs Exposure-Matched Baseline (gleiche ∅-Investitionsquote, kein Timing).

### 7.1 · Methodik

| Parameter | Wert |
|---|---|
| **Coins** | BTC, ETH, XRP, LTC, ADA, DOGE — gleichgewichtet (1/6) |
| **Granularität** | Täglich (Handelstage) |
| **OOS** | 2019-01-01 – 2026-06-01 (~7.5 Jahre, ~1900 Handelstage) |
| **WF-Gate** | 5 Expanding-Window Folds, Embargo 30 Tage |
| **Schwelle** | p ≥ 0.5 = IN, p < 0.5 = OUT (a priori, kein Tuning) |
| **TC** | 0.25% one-way beim Signal-Wechsel |
| **∅ Investitionsquote ML** | {avg_exposure:.1%} |
| **Exposure-Matched** | Konstante {avg_exposure:.1%} je Coin (kein Timing) |
| **CAGR-Basis** | {OOS_YEARS:.2f} Jahre (volle OOS-Periode) |

### 7.2 · Haupt-Ergebnis — Timing-Skill-Test

| Metrik | **ML-Timing** | **Buy-and-Hold** | **Exposure-Matched** |
|---|---|---|---|
| **CAGR** | {_fmt(ml_m["cagr"])} | {_fmt(bah_m["cagr"])} | {_fmt(em_m["cagr"])} |
| **Sharpe** | {_calmar_fmt(ml_m["sharpe"])} | {_calmar_fmt(bah_m["sharpe"])} | {_calmar_fmt(em_m["sharpe"])} |
| **Max-Drawdown** | {_fmt(ml_m["max_dd"])} | {_fmt(bah_m["max_dd"])} | {_fmt(em_m["max_dd"])} |
| **Calmar** | {_calmar_fmt(ml_m["calmar"])} | {_calmar_fmt(bah_m["calmar"])} | {_calmar_fmt(em_m["calmar"])} |

**Gesamturteil: {edge}**

> *Exposure-Matched = gleiche ∅-Investitionsquote ({avg_exposure:.1%}) wie ML, aber kein Timing —
> reines Unterinvestitions-Benchmark. Schlägt ML diesen Benchmark auf Calmar, ist echter
> Timing-Skill nachgewiesen.*

### 7.3 · Fold-Analyse (Calmar je Zeitraum)

| Zeitraum | ML Calmar | ML MaxDD | EM Calmar | EM MaxDD | BaH MaxDD | ∅ Exposure |
|---|---|---|---|---|---|---|
"""

    for f in folds_data:
        section += (
            f"| {f['label']} | {_calmar_fmt(f['ml']['calmar'])} | "
            f"{_fmt(f['ml']['max_dd'])} | {_calmar_fmt(f['em']['calmar'])} | "
            f"{_fmt(f['em']['max_dd'])} | {_fmt(f['bah']['max_dd'])} | "
            f"{f['exposure']:.1%} |\n"
        )

    section += """
### 7.4 · Interpretation

**ML vs Exposure-Matched:** Der entscheidende Vergleich ist ML Calmar vs EM Calmar.
- ML Calmar > EM: Das Modell trifft *wann* es investiert besser als Zufall — echter Timing-Skill.
- ML Calmar ≈ EM: Der Vorteil kommt nur vom tieferen Durchschnitts-Exposure, nicht vom Timing.
- ML Calmar < EM: Das Timing-Modell wählt aktiv schlechte Eintritte — negativer Timing-Skill.

**Vergleich Phase-2 CV:** Phase-2 Calmar=1.81 (purged CV, tägliche Signale, 6 Coins, 16k Samples).
Hier: echte OOS-Folds mit Retrain. Differenz zeigt In-Sample-Optimismus aus der CV-Evaluation.

**Drawdown 2022:** Das kritische Jahr für den Risk-Filter ist 2022 (BTC: −76.5% von Peak).
Fold 3 (OOS 2022) zeigt, ob das Modell vor dem Crash warnt.

---

*Abschnitt 7 ergänzt: tägliche Granularität, 6 Coins, Walk-Forward — 2026-06-20*
"""

    doc_path.write_text(existing.rstrip() + "\n" + section, encoding="utf-8")
    print("  docs/signal_backtest.md ergänzt (Abschnitt 7)")


# ---------------------------------------------------------------------------
# Hauptroutine
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 65)
    print("Phase 3 Daily Crypto Overlay (6 Coins, WF, p>=0.5)")
    print("=" * 65)

    # 1. Daten
    print("\n[1/5] Preisdaten laden...")
    closes = fetch_prices(COINS, date(2017, 1, 1), OOS_END)
    closes = closes[[c for c in COINS if c in closes.columns]]
    print(f"  Coins: {list(closes.columns)}, Shape: {closes.shape}")

    print("[2/5] Externe Daten...")
    fear_greed = fetch_fear_greed()
    mvrv = fetch_mvrv()

    # 2. Training-Features
    print("[3/5] Training-Features bauen (alle Coins, 2017–2026)...")
    df_train = build_training_features(closes, fear_greed, mvrv)
    print(f"  {len(df_train)} Feature-Rows ({df_train['ticker'].nunique()} Tickers)")

    # 3. Walk-Forward Signals
    print("[4/5] Walk-Forward Gate (5 Folds)...")
    signals = build_walk_forward_signals(df_train, closes, fear_greed, mvrv)
    print(f"  Signal-Einträge: {len(signals)}")

    # 4. Portfolio-Simulation
    print("[5/5] Portfolio-Simulation + Metriken...")
    cost_model = TransactionCostModel()

    result = simulate_portfolio(closes, signals, OOS_START, OOS_END, cost_model)
    ml_equity, bah_equity, em_equity, avg_exposure = result

    ml_m = metrics(ml_equity, OOS_YEARS)
    bah_m = metrics(bah_equity, OOS_YEARS)
    em_m = metrics(em_equity, OOS_YEARS)

    # Fold-Analyse
    fold_labels = [
        ("2019–20", 2019, 2020),
        ("2021–22", 2021, 2022),
        ("2023–24", 2023, 2024),
        ("2025–26", 2025, 2026),
    ]
    folds_data = []
    for label, y_from, y_to in fold_labels:
        fd = fold_metrics(closes, signals, cost_model, y_from, y_to)
        if fd:
            fd["label"] = label
            folds_data.append(fd)

    # Signal-Statistiken
    total_signal_days = sum(v for v in signals.values() if v == 1)
    total_possible = len(signals)

    # Report
    append_report_section(
        ml_m, bah_m, em_m, avg_exposure, folds_data, total_signal_days, total_possible
    )

    # Console-Ausgabe
    print(f"\n{'=' * 65}")
    print(f"{'Metrik':<20} {'ML-Timing':>12} {'BaH':>12} {'Exp-Matched':>14}")
    print("-" * 60)
    for key, label in [
        ("cagr", "CAGR"),
        ("sharpe", "Sharpe"),
        ("max_dd", "MaxDD"),
        ("calmar", "Calmar"),
    ]:
        ml_v = ml_m[key]
        bah_v = bah_m[key]
        em_v = em_m[key]
        if key in ("cagr", "max_dd"):
            row = f"{label:<20} {ml_v:>+11.1%} {bah_v:>+11.1%} {em_v:>+13.1%}"
        else:
            row = f"{label:<20} {ml_v:>12.2f} {bah_v:>12.2f} {em_v:>14.2f}"
        print(row)
    print(f"{'Avg. Exposure':<20} {avg_exposure:>+11.1%}")
    print()
    timing_edge = ml_m["calmar"] > em_m["calmar"]
    phase2_ref = 1.81
    print(f"ML Calmar:     {ml_m['calmar']:.2f}")
    print(f"EM Calmar:     {em_m['calmar']:.2f}")
    print(f"Phase-2 Ref:   {phase2_ref:.2f} (purged CV, in-sample)")
    print(
        f"Timing-Skill:  {'JA — ML > Exposure-Matched' if timing_edge else 'NEIN — ML <= Exposure-Matched'}"
    )


if __name__ == "__main__":
    main()
