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

from backend.application.backtest.walkforward import run_walkforward as _run_walkforward_sync
from backend.application.signals import signal_service
from backend.interfaces.rest.schemas.signals import BacktestReport, SignalVector

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
    prices_with_close.columns = ["close"]  # type: ignore[assignment]
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
