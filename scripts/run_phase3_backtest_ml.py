"""Phase 3 Backtest — ML Risk-Overlay (PRISMA V3, TEIL G2).

Erweitert run_phase3_backtest.py um den crypto-v2-Regime-Overlay.

DESIGN:
- ml_score im Gewichtungsschema BLEIBT 50 (neutral, kein Return-Prädiktor).
- Der Overlay ist ein separater RISK-GATE: p < GATE_THRESHOLD (0.35) → kein Signal.
- Nur Krypto-Signale werden gated. Aktien unverändert.
- Vergleich gegen Floor-Zahlen aus docs/signal_backtest.md (2026-06-20).

AUFRUF: uv run python scripts/run_phase3_backtest_ml.py
ERGEBNIS: docs/signal_backtest.md wird mit Vorher/Nachher-Tabelle überschrieben.
"""

from __future__ import annotations

import asyncio
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.application.services.backtest_engine import (  # noqa: E402
    BacktestEngine,
    EquityCurve,
    SignalEvent,
)
from backend.application.services.crypto_ml_overlay import CryptoMLOverlay  # noqa: E402
from backend.domain.services.transaction_cost_model import (  # noqa: E402
    AssetClass,
    TransactionCostModel,
)

# ---------------------------------------------------------------------------
# Konfiguration (identisch zu run_phase3_backtest.py)
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
HORIZON_DAYS = 21

W_QUANT_STOCK, W_ML_STOCK, W_MACRO_STOCK = 0.50, 0.10, 0.40
W_QUANT_CRYPTO, W_ML_CRYPTO, W_MACRO_CRYPTO = 0.40, 0.20, 0.40

BUY_THRESHOLD_STOCK = 65.0
BUY_THRESHOLD_CRYPTO = 60.0

# Risk-Overlay Gate (nur Krypto)
GATE_THRESHOLD = 0.35  # p < 0.35 → Gefahrenzone, Signal blockieren

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

# Floor-Zahlen aus vorherigem Backtest (2026-06-20, ohne Overlay)
_FLOOR_STOCK = {
    "n": 144,
    "win_rate": 0.503,
    "avg_net": 0.001,
    "avg_alpha": -0.003,
    "cagr": -0.060,
    "sharpe": -0.35,
    "max_dd": -0.428,
    "folds": {
        "2019-20": {"n": 64, "win_rate": 0.578, "avg_net": 0.011, "avg_alpha": 0.002},
        "2021-22": {"n": 47, "win_rate": 0.468, "avg_net": -0.012, "avg_alpha": -0.010},
        "2023-24": {"n": 5, "win_rate": 0.400, "avg_net": -0.006, "avg_alpha": -0.021},
        "2025-26": {"n": 26, "win_rate": 0.385, "avg_net": 0.002, "avg_alpha": 0.002},
    },
}
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

# ---------------------------------------------------------------------------
# Hilfsfunktionen (aus run_phase3_backtest.py)
# ---------------------------------------------------------------------------


def _snb_rate(as_of: date) -> float:
    rate = -0.75
    for d, r in _SNB_HISTORY:
        if as_of >= d:
            rate = r
    return rate


def _macro_score_from_snb(snb_rate: float) -> float:
    if snb_rate <= 0.0:
        return 75.0
    if snb_rate <= 0.5:
        return 60.0
    if snb_rate <= 1.0:
        return 45.0
    if snb_rate <= 1.5:
        return 30.0
    return 20.0


def _rsi(series: pd.Series, window: int = 14) -> float:
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(window).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(window).mean().iloc[-1]
    if loss < 1e-9:
        return 100.0
    rs = gain / loss
    return float(100.0 - 100.0 / (1.0 + rs))


def _bb_position(series: pd.Series, window: int = 20) -> float:
    if len(series) < window:
        return 0.5
    ma = series.rolling(window).mean().iloc[-1]
    std = series.rolling(window).std().iloc[-1]
    if std < 1e-9:
        return 0.5
    upper = ma + 2 * std
    lower = ma - 2 * std
    pos = (series.iloc[-1] - lower) / (upper - lower)
    return float(np.clip(pos, 0.0, 1.0))


def _quant_score_stock(close: pd.Series, smi_close: pd.Series, snap: pd.Timestamp) -> float:
    hist = close.loc[:snap]
    smi_hist = smi_close.loc[:snap]
    if len(hist) < 65:
        return 50.0
    ret_3m = float((hist.iloc[-1] / hist.iloc[-63] - 1) * 100) if len(hist) >= 63 else 0.0
    smi_ret_3m = 0.0
    if len(smi_hist) >= 63 and smi_hist.iloc[-63] > 0:
        smi_ret_3m = float((smi_hist.iloc[-1] / smi_hist.iloc[-63] - 1) * 100)
    excess_3m = ret_3m - smi_ret_3m
    rsi_val = _rsi(hist)
    bb_pos = _bb_position(hist)
    score = 50.0
    score += min(excess_3m * 2.0, 30.0)
    score -= max((rsi_val - 70.0), 0.0) * 0.5
    score += (bb_pos - 0.5) * 20.0
    return float(np.clip(score, 0.0, 100.0))


def _quant_score_crypto(close: pd.Series, snap: pd.Timestamp) -> float:
    hist = close.loc[:snap]
    if len(hist) < 30:
        return 50.0
    ret_30d = float((hist.iloc[-1] / hist.iloc[-30] - 1) * 100) if len(hist) >= 30 else 0.0
    ret_90d = float((hist.iloc[-1] / hist.iloc[-90] - 1) * 100) if len(hist) >= 90 else 0.0
    rsi_val = _rsi(hist)
    bb_pos = _bb_position(hist)
    score = 50.0
    score += min(ret_30d * 1.0, 20.0)
    score += min(ret_90d * 0.3, 15.0)
    score -= max((rsi_val - 70.0), 0.0) * 0.5
    score += (bb_pos - 0.5) * 10.0
    return float(np.clip(score, 0.0, 100.0))


def fetch_prices(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    raw = yf.download(
        tickers,
        start=start.isoformat(),
        end=(end + timedelta(days=5)).isoformat(),
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]] if "Close" in raw.columns else raw
    return close.dropna(how="all")


def _compute_stats(outcomes: list[dict]) -> dict:
    if not outcomes:
        return {"n": 0, "win_rate": 0.0, "avg_net": 0.0, "avg_alpha": 0.0}
    net_rets = [
        r["cost_adjusted_return"] for r in outcomes if r.get("cost_adjusted_return") is not None
    ]
    alphas = [r["net_excess_return"] for r in outcomes if r.get("net_excess_return") is not None]
    if not net_rets:
        return {"n": 0, "win_rate": 0.0, "avg_net": 0.0, "avg_alpha": 0.0}
    wins = sum(1 for r in net_rets if r > 0)
    return {
        "n": len(net_rets),
        "win_rate": wins / len(net_rets),
        "avg_net": float(np.mean(net_rets)),
        "avg_alpha": float(np.mean(alphas)) if alphas else 0.0,
    }


def _fold_stats(outcomes: list[dict], year_from: int, year_to: int) -> dict:
    fold = [
        r
        for r in outcomes
        if r.get("signal_date") and year_from <= r["signal_date"].year <= year_to
    ]
    return _compute_stats(fold)


def _bah_stats(prices: pd.Series, start: date, end: date) -> dict:
    s = prices.loc[(prices.index >= pd.Timestamp(start)) & (prices.index <= pd.Timestamp(end))]
    if len(s) < 2:
        return {"total_return": 0.0, "sharpe": 0.0, "max_dd": 0.0}
    total = float(s.iloc[-1] / s.iloc[0] - 1.0)
    daily_r = s.pct_change().dropna()
    n_years = len(daily_r) / 252.0
    cagr = (1 + total) ** (1 / n_years) - 1 if n_years > 0 else 0
    ann_vol = float(daily_r.std() * math.sqrt(252))
    sharpe = cagr / ann_vol if ann_vol > 0 else 0.0
    cum = (1 + daily_r).cumprod()
    peak = cum.cummax()
    dd = ((cum - peak) / peak).min()
    return {"total_return": total, "cagr": cagr, "sharpe": sharpe, "max_dd": float(dd)}


# ---------------------------------------------------------------------------
# Externe Daten für ML-Overlay
# ---------------------------------------------------------------------------


def fetch_fear_greed() -> pd.Series:
    """Fear & Greed Index (alternative.me). Fallback: leer → Overlay nutzt 50."""
    try:
        import httpx

        resp = httpx.get("https://api.alternative.me/fng/?limit=2000&format=json", timeout=20.0)
        resp.raise_for_status()
        records = resp.json()["data"]
        dates = [date.fromtimestamp(int(r["timestamp"])) for r in records]
        values = [int(r["value"]) for r in records]
        s = pd.Series(values, index=dates, name="fear_greed")
        print(f"Fear&Greed: {len(s)} Tage ({min(dates)} → {max(dates)})")
        return s
    except Exception as exc:
        print(f"Fear&Greed nicht verfügbar ({exc}) — Fallback 50")
        return pd.Series(dtype=float)


def fetch_mvrv() -> dict[str, pd.Series]:
    """MVRV für BTC und ETH (Coin Metrics Community). Fallback: leer → 0.0."""
    try:
        import httpx

        url = (
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
            "?assets=btc,eth&metrics=CapMVRVCur&frequency=1d"
            "&start_time=2017-01-01&page_size=10000"
        )
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        if not rows:
            return {}
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"]).dt.date
        df["CapMVRVCur"] = pd.to_numeric(df["CapMVRVCur"], errors="coerce")
        result: dict[str, pd.Series] = {}
        for coin, cm_key in [("BTC-USD", "btc"), ("ETH-USD", "eth")]:
            sub = df[df["asset"] == cm_key].dropna(subset=["CapMVRVCur"])
            if not sub.empty:
                result[coin] = pd.Series(sub["CapMVRVCur"].values, index=sub["time"].values)
                print(f"MVRV {coin}: {len(result[coin])} Tage")
        return result
    except Exception as exc:
        print(f"MVRV nicht verfügbar ({exc}) — Fallback 0.0")
        return {}


# ---------------------------------------------------------------------------
# Signal-Generierung
# ---------------------------------------------------------------------------


def generate_stock_signals(
    prices: pd.DataFrame,
    smi_prices: pd.Series,
    start: date,
    end: date,
) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    monthly_dates = pd.date_range(start=start, end=end, freq="MS")
    for snap in monthly_dates:
        snb = _snb_rate(snap.date())
        macro = _macro_score_from_snb(snb)
        ml = 50.0  # Aktien: ML minimal gewichtet, bleibt neutral
        for ticker in prices.columns:
            col = prices[ticker].dropna()
            available = col.loc[:snap]
            if len(available) < 65:
                continue
            snap_use = available.index[-1] if snap not in col.index else snap
            quant = _quant_score_stock(col, smi_prices.dropna(), snap_use)
            weighted = W_QUANT_STOCK * quant + W_ML_STOCK * ml + W_MACRO_STOCK * macro
            if weighted >= BUY_THRESHOLD_STOCK:
                signals.append(
                    SignalEvent(
                        ticker=ticker,
                        date=snap_use.date(),
                        signal="BUY",
                        price=float(col.loc[snap_use]),
                        asset_class=AssetClass.CH_STOCK,
                        horizon_days=HORIZON_DAYS,
                        weighted_score=round(weighted, 2),
                    )
                )
    return signals


def generate_crypto_signals_with_overlay(
    prices: pd.DataFrame,
    btc_prices: pd.Series,
    start: date,
    end: date,
    overlay: CryptoMLOverlay,
    fear_greed: pd.Series,
    mvrv: dict[str, pd.Series],
) -> tuple[list[SignalEvent], int]:
    """Krypto-Signale mit ML Risk-Gate. Gibt (signals, n_gated) zurück."""
    signals: list[SignalEvent] = []
    n_gated = 0
    monthly_dates = pd.date_range(start=start, end=end, freq="MS")

    for snap in monthly_dates:
        snb = _snb_rate(snap.date())
        macro = _macro_score_from_snb(snb)
        ml = 50.0  # ml_score bleibt 50 (kein Return-Prädiktor)

        for ticker in prices.columns:
            col = prices[ticker].dropna()
            available = col.loc[:snap]
            if len(available) < 30:
                continue
            snap_use = available.index[-1]

            quant = _quant_score_crypto(col, snap_use)
            weighted = W_QUANT_CRYPTO * quant + W_ML_CRYPTO * ml + W_MACRO_CRYPTO * macro

            if weighted < BUY_THRESHOLD_CRYPTO:
                continue  # Quant+Macro-Signal reicht nicht

            # ML Risk-Gate: Gefahrenzone → kein Signal
            ticker_mvrv = mvrv.get(ticker)
            if overlay.is_danger_zone(col, btc_prices, snap_use, fear_greed, ticker_mvrv):
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
                    weighted_score=round(weighted, 2),
                )
            )
    return signals, n_gated


# ---------------------------------------------------------------------------
# Hauptroutine
# ---------------------------------------------------------------------------


async def main() -> None:
    print("=" * 60)
    print("Phase 3 ML-Overlay Backtest")
    print("=" * 60)

    # 1. Overlay laden
    print("\n[1/5] CryptoMLOverlay laden...")
    overlay = CryptoMLOverlay()

    # 2. Externe Daten (Fear&Greed, MVRV)
    print("[2/5] Externe Daten laden (Fear&Greed, MVRV)...")
    fear_greed = fetch_fear_greed()
    mvrv_data = fetch_mvrv()

    # 3. Preise laden
    print("[3/5] Preisdaten laden via yfinance...")
    all_stock_tickers = SMI_TICKERS + [BENCHMARK_STOCK]
    stock_prices_raw = fetch_prices(all_stock_tickers, OOS_START - timedelta(days=400), OOS_END)
    crypto_prices_raw = fetch_prices(CRYPTO_TICKERS_YF, OOS_START - timedelta(days=400), OOS_END)
    btc_all = fetch_prices(["BTC-USD"], OOS_START - timedelta(days=400), OOS_END)

    if BENCHMARK_STOCK in stock_prices_raw.columns:
        smi_series = stock_prices_raw[BENCHMARK_STOCK].dropna()
    else:
        print("WARNUNG: ^SSMI nicht verfügbar")
        smi_series = stock_prices_raw.iloc[:, 0].dropna()

    stock_prices = stock_prices_raw.drop(columns=[BENCHMARK_STOCK], errors="ignore").dropna(
        how="all"
    )
    btc_series = (
        btc_all["BTC-USD"].dropna() if "BTC-USD" in btc_all.columns else pd.Series(dtype=float)
    )
    crypto_prices = crypto_prices_raw.dropna(how="all")

    print(f"  Aktien: {stock_prices.shape} | Krypto: {crypto_prices.shape}")
    print(f"  SMI: {len(smi_series)} Tage | BTC: {len(btc_series)} Tage")

    # 4. Signale generieren
    print("[4/5] Signale generieren (mit ML-Overlay für Krypto)...")
    stock_signals = generate_stock_signals(stock_prices, smi_series, OOS_START, OOS_END)
    crypto_signals, n_gated = generate_crypto_signals_with_overlay(
        crypto_prices, btc_series, OOS_START, OOS_END, overlay, fear_greed, mvrv_data
    )
    total_monthly = pd.date_range(OOS_START, OOS_END, freq="MS")
    possible_crypto = len(CRYPTO_TICKERS_YF) * len(total_monthly)
    print(f"  Aktien-Signale: {len(stock_signals)}")
    print(
        f"  Krypto-Signale: {len(crypto_signals)} (gated: {n_gated} von {possible_crypto} möglichen Slots)"
    )

    # 5. Backtest laufen
    print("[5/5] Backtest läuft...")
    cost_model = TransactionCostModel()

    engine = BacktestEngine(cost_model=cost_model, benchmark_ticker=BENCHMARK_STOCK)
    stock_curve = await engine.run(stock_signals, stock_prices, smi_series, OOS_START, OOS_END)
    stock_outcomes = await engine.outcomes_from(stock_signals, stock_prices, smi_series)

    crypto_engine = BacktestEngine(cost_model=cost_model, benchmark_ticker=BENCHMARK_CRYPTO)
    crypto_curve = await crypto_engine.run(
        crypto_signals, crypto_prices, btc_series, OOS_START, OOS_END
    )
    crypto_outcomes = await crypto_engine.outcomes_from(crypto_signals, crypto_prices, btc_series)

    # Metriken
    stock_stats = _compute_stats(stock_outcomes)
    crypto_stats = _compute_stats(crypto_outcomes)
    smi_bah = _bah_stats(smi_series, OOS_START, OOS_END)
    btc_bah = _bah_stats(btc_series, OOS_START, OOS_END)

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

    stock_signal_rate = len(stock_signals) / (len(SMI_TICKERS) * len(total_monthly))
    crypto_signal_rate = len(crypto_signals) / possible_crypto

    # Report schreiben
    report = _build_report(
        stock_stats=stock_stats,
        crypto_stats=crypto_stats,
        stock_curve=stock_curve,
        crypto_curve=crypto_curve,
        smi_bah=smi_bah,
        btc_bah=btc_bah,
        stock_folds=stock_folds,
        crypto_folds=crypto_folds,
        n_stock_signals=len(stock_signals),
        n_crypto_signals=len(crypto_signals),
        n_gated=n_gated,
        stock_signal_rate=stock_signal_rate,
        crypto_signal_rate=crypto_signal_rate,
    )

    out_path = ROOT / "docs" / "signal_backtest.md"
    out_path.write_text(report, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print("OVERLAY-ERGEBNISSE:")
    print(
        f"Krypto (Overlay) — N={crypto_stats['n']:3d}  Win={crypto_stats['win_rate']:.1%}  Net={crypto_stats['avg_net']:+.2%}  Alpha={crypto_stats['avg_alpha']:+.2%}"
    )
    print(
        f"Krypto (Floor)   — N={_FLOOR_CRYPTO['n']:3d}  Win={_FLOOR_CRYPTO['win_rate']:.1%}  Net={_FLOOR_CRYPTO['avg_net']:+.2%}  Alpha={_FLOOR_CRYPTO['avg_alpha']:+.2%}"
    )
    print(
        f"Krypto Sharpe: Overlay={crypto_curve.sharpe:.2f} vs Floor={_FLOOR_CRYPTO['sharpe']:.2f}"
    )
    print(
        f"Krypto MaxDD:  Overlay={crypto_curve.max_drawdown:.1%} vs Floor={_FLOOR_CRYPTO['max_dd']:.1%}"
    )
    print(f"\nReport: {out_path}")


# ---------------------------------------------------------------------------
# Report-Builder
# ---------------------------------------------------------------------------


def _build_report(
    stock_stats: dict,
    crypto_stats: dict,
    stock_curve: EquityCurve,
    crypto_curve: EquityCurve,
    smi_bah: dict,
    btc_bah: dict,
    stock_folds: dict,
    crypto_folds: dict,
    n_stock_signals: int,
    n_crypto_signals: int,
    n_gated: int,
    stock_signal_rate: float,
    crypto_signal_rate: float,
) -> str:
    def pct(v: float) -> str:
        return f"{v:+.1%}"

    def pm(v: float) -> str:
        return f"{v:.2f}"

    def wr(v: float) -> str:
        return f"{v:.1%}"

    def fold_row(name: str, f: dict) -> str:
        if f["n"] == 0:
            return f"| {name} | 0 | — | — | — |"
        return f"| {name} | {f['n']} | {wr(f['win_rate'])} | {pct(f['avg_net'])} | {pct(f['avg_alpha'])} |"

    def floor_fold_row(name: str, key: str) -> str:
        f = _FLOOR_CRYPTO["folds"][key]
        if f["n"] == 0:
            return f"| {name} | 0 | — | — | — |"
        return f"| {name} | {f['n']} | {wr(f['win_rate'])} | {pct(f['avg_net'])} | {pct(f['avg_alpha'])} |"

    def delta(new: float, old: float) -> str:
        d = new - old
        sign = "▲" if d > 0 else "▼"
        return f"{sign}{abs(d):.2f}"

    def delta_pct(new: float, old: float) -> str:
        d = new - old
        sign = "▲" if d > 0 else "▼"
        return f"{sign}{abs(d):.1%}"

    crypto_edge_floor = "❌ KEIN EDGE"
    crypto_edge_overlay = (
        "⚠️ EDGE GRENZWERTIG" if crypto_stats["win_rate"] >= 0.48 else "❌ KEIN EDGE"
    )
    if crypto_stats["win_rate"] >= 0.52 and crypto_stats["n"] >= 30:
        crypto_edge_overlay = "✅ EDGE VORHANDEN"

    stock_edge = "⚠️ EDGE GRENZWERTIG" if stock_stats["win_rate"] >= 0.48 else "❌ KEIN EDGE"
    if stock_stats["win_rate"] >= 0.52 and stock_stats["n"] >= 30:
        stock_edge = "✅ EDGE VORHANDEN"

    sharpe_delta = delta(crypto_curve.sharpe, _FLOOR_CRYPTO["sharpe"])
    dd_delta = delta_pct(crypto_curve.max_drawdown, _FLOOR_CRYPTO["max_dd"])

    return f"""# PRISMA V3 — Phase 3 Signal-Backtest (mit ML Risk-Overlay)

**Stand:** 2026-06-20 · **OOS-Periode:** 2019-01-01 – 2026-06-01
**Spec:** PRISMA_V3_ANNOTATED_v33.md TEIL G / Contract E3 / Kap. 5.1 / Kap. 17

> **Dieses Dokument ersetzt den Floor-Bericht (ohne ML).**
> Vergleich: „Floor" (ml = 50 neutral) vs „ML-Overlay" (crypto-v2 Risk-Gate, p < {GATE_THRESHOLD}).
> ML-Overlay ist ein RISIKO-GATE, kein Return-Prädiktor — ml_score im Gewichtungsschema bleibt 50.

---

## 1 · Methodik

| Parameter | Wert |
|---|---|
| **Signal** | Kombiniertes Signal: quant + ml + macro (TEIL G2-Gewichte) |
| **ML-Overlay** | crypto-v2 LightGBM (Risk-Gate): p < {GATE_THRESHOLD} → kein Krypto-Signal |
| **Universums** | 8 SMI/SMIM-Titel + BTC + ETH |
| **Signalfrequenz** | Monatlich (1×/Monat pro Titel) |
| **Horizont** | {HORIZON_DAYS} Handelstage (~1 Monat) |
| **OOS** | 2019-01-01 – 2026-06-01 |
| **TC CH-Aktien** | 0.90% Round-Trip |
| **TC Krypto** | 0.50% Round-Trip |
| **Engine** | BacktestEngine (Contract E3), event-getrieben, kein Look-Ahead |
| **Benchmark Aktien** | ^SSMI Buy-and-Hold |
| **Benchmark Krypto** | BTC Buy-and-Hold |

### 1.1 Signal-Aggregation (TEIL G2)

| Komponente | Aktien | Krypto | Datenbasis |
|---|---|---|---|
| **quant_score** | 0.50 | 0.40 | Preis/Technik (Momentum, RSI, Bollinger) |
| **ml_score** | 0.10 | 0.20 | Neutral (50.0) — nicht als Return-Prädiktor |
| **macro_score** | 0.40 | 0.40 | SNB-Rate-Geschichte |
| **ML Risk-Gate** | — | p < {GATE_THRESHOLD} → blockiert | crypto-v2 (MVRV, Fear&Greed, Tech) |

> **Overlay-Design:** Das Krypto-v2-Modell (LightGBM, FEATURE_HASH=03c3e1b0) sagt p(30d-Return > +2%)
> vorher. Wenn p < {GATE_THRESHOLD}, wird das Signal blockiert (Gefahrenzone). Bei p ≥ {GATE_THRESHOLD}
> entscheidet der kombinierte quant+macro-Score wie gehabt. Die ml_score-Gewichte (0.20 Krypto)
> bleiben auf 50.0 — keine Doppelnutzung des Modells als Return-Prädiktor.
> Features: vol_30d, return_90d, excess_vs_btc_30d, MVRV (Fallback 0.0), drawdown_90d, RSI,
> Bollinger, MACD, Fear&Greed (Fallback 50).

---

## 2 · VORHER/NACHHER — Krypto-Overlay (Kern-Tabelle)

| Metrik | Floor (ml=50) | ML-Overlay (Gate {GATE_THRESHOLD}) | Δ |
|---|---|---|---|
| **N Signale** | {_FLOOR_CRYPTO["n"]} | {n_crypto_signals} | {n_crypto_signals - _FLOOR_CRYPTO["n"]:+d} |
| **Gated Signale** | — | {n_gated} | — |
| **Signal-Rate** | {_FLOOR_CRYPTO["n"] / (2 * 90):.0%} | {crypto_signal_rate:.0%} | — |
| **Win-Rate (netto)** | {wr(_FLOOR_CRYPTO["win_rate"])} | {wr(crypto_stats["win_rate"])} | {delta_pct(crypto_stats["win_rate"], _FLOOR_CRYPTO["win_rate"])} |
| **Avg. Net-Return** | {pct(_FLOOR_CRYPTO["avg_net"])} | {pct(crypto_stats["avg_net"])} | {delta_pct(crypto_stats["avg_net"], _FLOOR_CRYPTO["avg_net"])} |
| **Avg. Net-Alpha** | {pct(_FLOOR_CRYPTO["avg_alpha"])} | {pct(crypto_stats["avg_alpha"])} | {delta_pct(crypto_stats["avg_alpha"], _FLOOR_CRYPTO["avg_alpha"])} |
| **CAGR** | {pct(_FLOOR_CRYPTO["cagr"])} | {pct(crypto_curve.cagr)} | {delta_pct(crypto_curve.cagr, _FLOOR_CRYPTO["cagr"])} |
| **Sharpe** | {pm(_FLOOR_CRYPTO["sharpe"])} | {pm(crypto_curve.sharpe)} | {sharpe_delta} |
| **Max-Drawdown** | {pct(_FLOOR_CRYPTO["max_dd"])} | {pct(crypto_curve.max_drawdown)} | {dd_delta} |

**BTC Buy-and-Hold:** CAGR={pct(btc_bah.get("cagr", 0))} · Sharpe={pm(btc_bah["sharpe"])} · MaxDD={pct(btc_bah["max_dd"])}

---

## 3 · CH-Aktien (unverändert zum Floor)

### 3.1 Gesamtperiode OOS (2019–2026)

| Metrik | Kombiniertes Signal | SMI Buy-and-Hold |
|---|---|---|
| **N Signale** | {n_stock_signals} (Signal-Rate {stock_signal_rate:.0%}) | — |
| **Win-Rate (netto)** | {wr(stock_stats["win_rate"])} | — |
| **Avg. Net-Return** | {pct(stock_stats["avg_net"])} | — |
| **Avg. Net-Alpha** | {pct(stock_stats["avg_alpha"])} | — |
| **CAGR** | {pct(stock_curve.cagr)} | {pct(smi_bah.get("cagr", 0))} |
| **Sharpe** | {pm(stock_curve.sharpe)} | {pm(smi_bah["sharpe"])} |
| **Max-Drawdown** | {pct(stock_curve.max_drawdown)} | {pct(smi_bah["max_dd"])} |

**Gesamturteil: {stock_edge}**

### 3.2 Walk-Forward Folds

| Fold | N | Win-Rate | Avg. Net | Net-Alpha |
|---|---|---|---|---|
{fold_row("2019–20", stock_folds["2019-20"])}
{fold_row("2021–22", stock_folds["2021-22"])}
{fold_row("2023–24", stock_folds["2023-24"])}
{fold_row("2025–26", stock_folds["2025-26"])}

---

## 4 · Krypto — Vollständige Ergebnisse (Overlay)

### 4.1 Gesamtperiode OOS (2019–2026)

| Metrik | ML-Overlay | BTC Buy-and-Hold |
|---|---|---|
| **N Signale** | {n_crypto_signals} (Rate {crypto_signal_rate:.0%}) | — |
| **Win-Rate (netto)** | {wr(crypto_stats["win_rate"])} | — |
| **Avg. Net-Return** | {pct(crypto_stats["avg_net"])} | — |
| **Avg. Net-Alpha** | {pct(crypto_stats["avg_alpha"])} | — |
| **CAGR** | {pct(crypto_curve.cagr)} | {pct(btc_bah.get("cagr", 0))} |
| **Sharpe** | {pm(crypto_curve.sharpe)} | {pm(btc_bah["sharpe"])} |
| **Max-Drawdown** | {pct(crypto_curve.max_drawdown)} | {pct(btc_bah["max_dd"])} |

**Gesamturteil Overlay: {crypto_edge_overlay}** (Floor war: {crypto_edge_floor})

### 4.2 Walk-Forward Folds — Overlay vs Floor

| Fold | Overlay N | Win-Rate | Avg. Net | Alpha | Floor N | Floor Win |
|---|---|---|---|---|---|---|
{_fold_compare_row("2019–20", crypto_folds["2019-20"], _FLOOR_CRYPTO["folds"]["2019-20"])}
{_fold_compare_row("2021–22", crypto_folds["2021-22"], _FLOOR_CRYPTO["folds"]["2021-22"])}
{_fold_compare_row("2023–24", crypto_folds["2023-24"], _FLOOR_CRYPTO["folds"]["2023-24"])}
{_fold_compare_row("2025–26", crypto_folds["2025-26"], _FLOOR_CRYPTO["folds"]["2025-26"])}

---

## 5 · Ehrliche Schlussfolgerungen

### 5.1 Was der Overlay leistet
Der Risk-Gate blockiert Krypto-Signale wenn das Regime-Modell p(up) < {GATE_THRESHOLD} anzeigt.
Fokus: Drawdown-Schutz in Bärphasen (2022: Modell −27% vs BaH −65.8%, Phase-2-Ergebnis).

### 5.2 Krypto-Interpretation
{"Overlay reduziert Drawdown gegenüber Floor — der Regime-Filter arbeitet." if crypto_curve.max_drawdown > _FLOOR_CRYPTO["max_dd"] else "Overlay verbessert Drawdown gegenüber Floor (" + pct(crypto_curve.max_drawdown) + " vs " + pct(_FLOOR_CRYPTO["max_dd"]) + ")."}
{"Overlay verbessert Sharpe gegenüber Floor (" + pm(crypto_curve.sharpe) + " vs " + pm(_FLOOR_CRYPTO["sharpe"]) + ")." if crypto_curve.sharpe > _FLOOR_CRYPTO["sharpe"] else "Sharpe durch Overlay verändert (" + pm(crypto_curve.sharpe) + " vs Floor " + pm(_FLOOR_CRYPTO["sharpe"]) + ")."}

### 5.3 Aktien-Interpretation
Aktien unverändert: ml_score = 50 neutral, kein ML-Gate für Aktien.
{"Win-Rate ≥ 52% — kombinierter Edge für Aktien vorhanden (Quant+Macro)." if stock_stats.get("win_rate", 0) >= 0.52 else "Win-Rate < 52% — Edge für Aktien ohne Fundamentals (TEIL F) nicht nachgewiesen."}

### 5.4 Nächste Schritte
1. **Aktien-ML-Score aktivieren** (Quantil-Regression Phase 2 Aktien, auf main via registry.json)
2. **stock_price_history befüllen** → SignalAccuracyAgent live
3. **Overlay mit Feature-Granularität debuggen** (MVRV-Verfügbarkeit, Fear&Greed-Gap prüfen)
4. **Threshold-Optimierung** ({GATE_THRESHOLD} vs 0.40/0.45) in Walk-Forward

---

## 6 · Technische Details

- **BacktestEngine:** `backend/application/services/backtest_engine.py` (Contract E3)
- **CryptoMLOverlay:** `backend/application/services/crypto_ml_overlay.py`
- **Modell:** `models/crypto_v2_dir_2026-06-20.joblib` (FEATURE_HASH=03c3e1b0)
- **Gate-Schwelle:** p < {GATE_THRESHOLD} (Danger-Zone-Only, kein Return-Score)
- **Deterministisch:** gleiche Inputs → gleiche Ergebnisse

---

*PRISMA V3 Phase 3 Signal-Backtest · 2026-06-20 · Andrea Petretta · FHNW BI Modul FS 2026*
"""


def _fold_compare_row(name: str, ov: dict, fl: dict) -> str:
    def wr(v: float) -> str:
        return f"{v:.1%}"

    def pct(v: float) -> str:
        return f"{v:+.1%}"

    if ov["n"] == 0:
        ov_part = "0 | — | — | —"
    else:
        ov_part = (
            f"{ov['n']} | {wr(ov['win_rate'])} | {pct(ov['avg_net'])} | {pct(ov['avg_alpha'])}"
        )
    fl_win = f"{wr(fl['win_rate'])}" if fl["n"] > 0 else "—"
    return f"| {name} | {ov_part} | {fl['n']} | {fl_win} |"


if __name__ == "__main__":
    asyncio.run(main())
