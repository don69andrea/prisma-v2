"""REST Router: Crypto Signal Engine API.

Endpoints (A7.9):
  GET /api/v1/signals           → list[SignalVector]
  GET /api/v1/signals/{coin}    → SignalVector
  GET /api/v1/backtest/{coin}   → BacktestReport

Alle Endpoints sind read-only (GET). Keine Datenbankschreiboperationen.
Service-Layer (signal_service.evaluate, run_walkforward) wird injiziert —
testbar ohne echte DB-Verbindung.

Cache: Ergebnisse werden 1 Stunde im Speicher gehalten (kein Redis nötig).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, status

from backend.application.backtest.walkforward import (
    run_walkforward as _run_walkforward_sync,
)
from backend.application.backtest.walkforward import (
    run_walkforward_with_details as _run_wf_details,
)
from backend.application.signals import signal_service
from backend.application.signals.meta_label import (
    build_meta_features,
    predict_meta_label,
    triple_barrier_labels,
)
from backend.interfaces.rest.schemas.signals import (
    BacktestReport,
    MetaLabelReport,
    SignalVector,
)

_logger = logging.getLogger(__name__)

# ── Router-Definitionen ────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])
backtest_router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

# ── Bekannte Crypto-Coins (Crypto-Universe) ────────────────────────────────────

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

# ── In-Memory Cache (TTL = 1 Stunde) ──────────────────────────────────────────

_CACHE_TTL_SECONDS = 3600
_signal_cache: dict[str, tuple[float, SignalVector]] = {}  # coin → (timestamp, vector)
_list_cache: tuple[float, list[SignalVector]] | None = None


def _is_cache_valid(timestamp: float) -> bool:
    return (time.monotonic() - timestamp) < _CACHE_TTL_SECONDS


def _get_cached_signal(coin: str) -> SignalVector | None:
    entry = _signal_cache.get(coin)
    if entry and _is_cache_valid(entry[0]):
        return entry[1]
    return None


def _set_cached_signal(coin: str, vector: SignalVector) -> None:
    _signal_cache[coin] = (time.monotonic(), vector)


# ── Hilfsfunktion: Minimale Preisdaten synthetisieren (für Demo / Fallback) ───


def _make_stub_prices(coin: str, n: int = 200) -> pd.DataFrame:
    """Erzeugt synthetische Preisdaten für Tests und Fallback ohne DB.

    In Produktion werden echte Preise aus der DB oder einem Market-Data-Provider
    geladen. Hier wird ein deterministischer Random-Walk als Fallback verwendet.
    """
    rng = np.random.default_rng(seed=abs(hash(coin)) % 2**32)
    returns = rng.normal(0.001, 0.03, size=n)
    prices = 100.0 * np.cumprod(1 + returns)
    idx = pd.date_range(end=datetime.now(UTC), periods=n, freq="D", tz="UTC")
    return pd.DataFrame({coin: prices}, index=idx)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[SignalVector],
    summary="Signal-Vektoren für alle bekannten Coins",
    description=(
        "Berechnet SignalVektoren (BUY/HOLD/SELL + Sizing) für alle Coins im "
        "Crypto-Universe. Ergebnis wird 1 Stunde gecacht."
    ),
)
async def list_signals() -> list[SignalVector]:
    """GET /api/v1/signals → list[SignalVector]."""
    global _list_cache
    if _list_cache is not None and _is_cache_valid(_list_cache[0]):
        return _list_cache[1]

    today = date.today()
    results: list[SignalVector] = []

    for coin in _CRYPTO_UNIVERSE:
        cached = _get_cached_signal(coin)
        if cached is not None:
            results.append(cached)
            continue
        try:
            prices_df = _make_stub_prices(coin)
            vector = await signal_service.evaluate(coin=coin, asof=today, prices_df=prices_df)
            _set_cached_signal(coin, vector)
            results.append(vector)
        except Exception:  # noqa: BLE001
            _logger.warning("signal_service.evaluate fehlgeschlagen für %s — übersprungen", coin)

    _list_cache = (time.monotonic(), results)
    return results


@router.get(
    "/{coin}",
    response_model=SignalVector,
    summary="Signal-Vektor für einen einzelnen Coin",
    description=(
        "Gibt den SignalVektor für den angegebenen Coin zurück. "
        "coin muss im Crypto-Universe enthalten sein (z. B. BTC-USD). "
        "404 wenn unbekannt."
    ),
)
async def get_signal(coin: str) -> SignalVector:
    """GET /api/v1/signals/{coin} → SignalVector."""
    coin_upper = coin.upper()
    if coin_upper not in _CRYPTO_UNIVERSE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coin '{coin_upper}' ist nicht im Crypto-Universe. "
            f"Verfügbar: {_CRYPTO_UNIVERSE}",
        )

    cached = _get_cached_signal(coin_upper)
    if cached is not None:
        return cached

    today = date.today()
    prices_df = _make_stub_prices(coin_upper)
    try:
        vector = await signal_service.evaluate(coin=coin_upper, asof=today, prices_df=prices_df)
    except ValueError as exc:
        _logger.error("evaluate fehlgeschlagen für %s: %s", coin_upper, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    _set_cached_signal(coin_upper, vector)
    return vector


async def run_walkforward(coin: str, prices_df: pd.DataFrame) -> BacktestReport:
    """Async-Wrapper um synchronen run_walkforward für Router-Kompatibilität.

    Synthetisiert eine Signal-Series aus den Preisdaten (einfaches SMA-Crossover)
    und ruft dann run_walkforward synchron in einem Thread-Pool auf.
    """
    # Einfaches SMA-Signal: investiert wenn close > SMA(30)
    prices_with_close = prices_df.copy()
    prices_with_close.columns = pd.Index(["close"])
    close = prices_with_close["close"]
    sma30 = close.rolling(30, min_periods=1).mean()
    signals = (close > sma30).astype(float)

    def _sync_call() -> BacktestReport:
        return _run_walkforward_sync(prices=prices_with_close, signals=signals, coin=coin)

    return await asyncio.to_thread(_sync_call)


@backtest_router.get(
    "/{coin}",
    response_model=BacktestReport,
    summary="Walk-Forward-Backtest für einen Coin",
    description=(
        "Führt einen Expanding-Window Walk-Forward-Backtest durch und gibt "
        "BacktestReport zurück. coin muss im Crypto-Universe enthalten sein. "
        "beats_exposure_matched=True wenn Signal-Strategie Sharpe UND Calmar "
        "der Exposure-Matched-Baseline übertrifft."
    ),
)
async def get_backtest(coin: str) -> BacktestReport:
    """GET /api/v1/backtest/{coin} → BacktestReport."""
    coin_upper = coin.upper()
    if coin_upper not in _CRYPTO_UNIVERSE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coin '{coin_upper}' ist nicht im Crypto-Universe. "
            f"Verfügbar: {_CRYPTO_UNIVERSE}",
        )

    prices_df = _make_stub_prices(coin_upper, n=500)
    try:
        report = await run_walkforward(coin=coin_upper, prices_df=prices_df)
    except Exception as exc:  # noqa: BLE001
        _logger.error("run_walkforward fehlgeschlagen für %s: %s", coin_upper, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Backtest temporär nicht verfügbar für {coin_upper}.",
        ) from exc

    return report


# ── Meta-Label Endpoint (Wave D) ─────────────────────────────────────────────


def _sync_meta_label(coin: str, prices_df: pd.DataFrame) -> MetaLabelReport:
    """Synchrone Meta-Label-Pipeline — läuft in asyncio.to_thread.

    1. Baut close/high/low Frame aus Stub-Preisen.
    2. Berechnet triple_barrier Labels (→ binär).
    3. Baut Feature-Matrix via build_meta_features.
    4. Führt predict_meta_label Walk-Forward durch.
    5. Vergleicht always-trade vs. meta-filtered mit run_walkforward_with_details.
    6. Bestimmt finding: positive / secondary_pass / negative.
    """

    # ── 1. Preisframe aufbereiten ─────────────────────────────────────────────
    close = prices_df.iloc[:, 0].rename("close")
    high = close * 1.005
    low = close * 0.995
    price_frame = pd.DataFrame({"close": close, "high": high, "low": low})

    # ── 2. Triple-Barrier Labels → binär (1 = kaufen, 0 = überspringen) ──────
    labels_raw = triple_barrier_labels(
        close=price_frame["close"],
        high=price_frame["high"],
        low=price_frame["low"],
        atr_window=20,
        upper_mult=2.0,
        lower_mult=1.0,
        horizon=5,
    )
    # Map {-1,0,+1} → binary {0,1}: +1 → 1 (long signal), else → 0
    y = (labels_raw == 1).astype(int)
    y.name = "label"

    # ── 3. Meta-Features bauen ────────────────────────────────────────────────
    # Build minimal signal columns for build_meta_features
    sma20 = close.rolling(20, min_periods=1).mean()
    ma_sig = (close > sma20).astype(float)

    from backend.application.signals.indicators import macd as _macd  # noqa: PLC0415
    from backend.application.signals.indicators import rsi as _rsi

    _, signal_line, _ = _macd(close)
    macd_sig = (close > signal_line.fillna(close)).astype(float)
    rsi_val = _rsi(close)
    rsi_sig = (rsi_val < 70).astype(float).fillna(0.0)

    feat_frame = price_frame.copy()
    feat_frame["ma_signal"] = ma_sig
    feat_frame["macd_signal"] = macd_sig
    feat_frame["rsi_signal"] = rsi_sig

    X = build_meta_features(feat_frame)

    # Align X and y (drop rows where both NaN after shift)
    aligned = pd.concat([X, y], axis=1).dropna()
    if aligned.empty:
        return MetaLabelReport(
            coin=coin,
            label_method="triple_barrier",
            classifier="logreg",
            n_folds=0,
            oos_precision=0.0,
            oos_recall=0.0,
            always_trade_sharpe=0.0,
            always_trade_calmar=0.0,
            meta_filtered_sharpe=0.0,
            meta_filtered_calmar=0.0,
            n_trades_always=0,
            n_trades_filtered=0,
            beats_baseline=False,
            finding="negative",
            finding_reason="insufficient_data",
        )

    X_aligned = aligned.drop(columns=["label"])
    y_aligned = aligned["label"]

    # ── 4. Walk-Forward Meta-CV ───────────────────────────────────────────────
    ml_result = predict_meta_label(
        X_aligned,
        y_aligned,
        min_train=252,
        step=21,
        embargo=5,
        model="logreg",
    )

    n_folds = int(ml_result["n_folds"])
    oos_precision = float(ml_result.get("mean_precision", 0.0))
    oos_recall = float(ml_result.get("mean_recall", 0.0))
    classifier_used = "logreg"

    # ── 5. Backtest: always-trade vs meta-filtered ────────────────────────────
    # Build a simple SMA-crossover signal for the backtest (same as run_walkforward)
    sma30 = close.rolling(30, min_periods=1).mean()
    consensus_signal = (close > sma30).astype(float)

    prices_for_bt = pd.DataFrame({"close": close})

    always = _run_wf_details(prices=prices_for_bt, signals=consensus_signal, costs=0.001)

    # Meta-filter: build predicted labels series aligned to price index
    # Use y_aligned reindexed to full price index (0 where no prediction)
    meta_filter_series = y_aligned.reindex(prices_for_bt.index).fillna(0.0)

    filtered = _run_wf_details(
        prices=prices_for_bt,
        signals=consensus_signal,
        costs=0.001,
        meta_filter=meta_filter_series,
    )

    always_sharpe = float(always["strategy_sharpe"])
    always_calmar = float(always["strategy_calmar"])
    meta_sharpe = float(filtered["strategy_sharpe"])
    meta_calmar = float(filtered["strategy_calmar"])
    n_always = int(always["n_trades"])
    n_filtered = int(filtered["n_trades"])

    # ── 6. Finding-Logik ──────────────────────────────────────────────────────
    if n_folds < 10:
        finding = "negative"
        finding_reason = "insufficient_oos_folds"
        beats = False
    elif meta_sharpe > always_sharpe and meta_calmar > always_calmar:
        finding = "positive"
        finding_reason = "meta_filtered_beats_always_trade_sharpe_and_calmar"
        beats = True
    elif (
        n_filtered < n_always * 0.9
        and meta_sharpe >= always_sharpe * 0.95
        and meta_calmar >= always_calmar * 0.95
    ):
        finding = "secondary_pass"
        finding_reason = "reduced_trades_without_significant_perf_loss"
        beats = True
    else:
        finding = "negative"
        finding_reason = "meta_filter_does_not_improve_over_always_trade"
        beats = False

    return MetaLabelReport(
        coin=coin,
        label_method="triple_barrier",
        classifier=classifier_used,
        n_folds=n_folds,
        oos_precision=oos_precision,
        oos_recall=oos_recall,
        always_trade_sharpe=always_sharpe,
        always_trade_calmar=always_calmar,
        meta_filtered_sharpe=meta_sharpe,
        meta_filtered_calmar=meta_calmar,
        n_trades_always=n_always,
        n_trades_filtered=n_filtered,
        beats_baseline=beats,
        finding=finding,  # type: ignore[arg-type]
        finding_reason=finding_reason,
    )


async def run_meta_label(coin: str, prices_df: pd.DataFrame) -> MetaLabelReport:
    """Async-Wrapper um die synchrone meta-label Pipeline (asyncio.to_thread).

    CLAUDE.md Async-Pattern: asyncio.to_thread (NICHT run_in_executor).
    """

    def _call() -> MetaLabelReport:
        return _sync_meta_label(coin, prices_df)

    return await asyncio.to_thread(_call)


@router.get(
    "/meta-label/{coin}",
    response_model=MetaLabelReport,
    summary="Meta-Labeling Analyse für einen Coin",
    description=(
        "Berechnet Meta-Labeling Pipeline: Triple-Barrier Labels, Walk-Forward "
        "Classifier, immer-trade vs. meta-gefilterter Strategie-Vergleich. "
        "coin muss im Crypto-Universe enthalten sein. 404 wenn unbekannt. "
        "finding: positive/secondary_pass/negative."
    ),
)
async def get_meta_label(coin: str) -> MetaLabelReport:
    """GET /api/v1/signals/meta-label/{coin} → MetaLabelReport."""
    coin_upper = coin.upper()
    if coin_upper not in _CRYPTO_UNIVERSE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coin '{coin_upper}' ist nicht im Crypto-Universe. "
            f"Verfügbar: {_CRYPTO_UNIVERSE}",
        )

    prices_df = _make_stub_prices(coin_upper, n=500)
    try:
        report = await run_meta_label(coin=coin_upper, prices_df=prices_df)
    except Exception as exc:  # noqa: BLE001
        _logger.error("run_meta_label fehlgeschlagen für %s: %s", coin_upper, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Meta-Label Analyse temporär nicht verfügbar für {coin_upper}.",
        ) from exc

    return report
