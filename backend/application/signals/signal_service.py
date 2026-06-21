"""Signal Service: Orchestriert Layers 1-3 zu einem SignalVector pro Coin.

Kein I/O innerhalb von evaluate() — alle Daten werden injiziert (testbar ohne DB).

Architektur:
  Layer 1 (WAS): cross_sectional_momentum() + onchain_health_score()
  Layer 2 (WANN): SMA/MACD/RSI-Indikatoren + 2-of-3 consensus_vote()
  Layer 3 (WIEVIEL): predict_vol() + apply_sizing()
  Output: SignalVector (Pydantic)

Look-Ahead-Guard:
  prices_df wird auf asof_date gefiltert bevor irgendwelche Indikatoren berechnet werden.
  signal@t verwendet nur Daten ≤ t (kein Datenpunkt der Zukunft).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.application.signals.consensus import consensus_vote
from backend.application.signals.factors import (
    cross_sectional_momentum,
    onchain_health_score,
)
from backend.application.signals.indicators import macd, rsi, sma
from backend.application.signals.sizing import apply_sizing
from backend.application.signals.vol_forecast import predict_vol
from backend.interfaces.rest.schemas.signals import SignalVector

logger = logging.getLogger(__name__)

__all__ = ["evaluate"]

# Anzahl der Signale im 2-of-3 Consensus
_N_SIGNALS = 3

# Schwellwert für schlechtes Momentum-Ranking → SELL
# (Rank > Threshold = schlechtes Ranking, z. B. Coin #9 von 10)
_SELL_RANK_THRESHOLD = 8


async def evaluate(
    coin: str,
    asof: date,
    prices_df: pd.DataFrame,
    onchain_df: pd.DataFrame | None = None,
    vol_model_info: dict[str, Any] | None = None,
) -> SignalVector:
    """Berechne den SignalVector für einen Coin zum angegebenen Stichtag.

    Kein I/O innerhalb dieser Funktion — alle Daten werden als Parameter übergeben.
    Dies ermöglicht Testing ohne Datenbankverbindung.

    Parameters
    ----------
    coin:
        Coin-Symbol (muss als Spalte in prices_df vorhanden sein).
    asof:
        Stichtag. Nur Daten ≤ asof werden verwendet (Look-Ahead-Guard).
    prices_df:
        Preismatrix (Spalten = Coins, Index = DatetimeIndex, Werte = Close-Preise).
    onchain_df:
        Optionales On-Chain-DataFrame mit Spalten: coin_id, date, mvrv_z, active_addresses.
        Falls None → onchain_score = 0.5 (neutral).
    vol_model_info:
        Optionales Modell-Info-Dict aus fit_walkforward() für diesen Coin.
        Falls None → pred_vol = 0.60 (Fallback-Schätzung).

    Returns
    -------
    SignalVector
        Vollständiger Signal-Vektor mit action, size_factor, sub_scores etc.

    Raises
    ------
    ValueError
        Wenn coin nicht in prices_df.columns vorhanden ist oder zu wenig Daten vorliegen.
    """
    # ── Look-Ahead-Guard: Nur Daten bis asof verwenden ───────────────────────
    # Timezone-aware Timestamp: falls Index UTC-aware ist, muss asof_ts auch UTC sein.
    asof_ts = pd.Timestamp(asof, tz="UTC")
    if prices_df.index.tz is None:
        # Index ist tz-naive — Timestamp ohne tz für Vergleich
        asof_ts = pd.Timestamp(asof)
    prices_filtered = prices_df[prices_df.index <= asof_ts].copy()

    if coin not in prices_filtered.columns:
        raise ValueError(
            f"Coin '{coin}' nicht in prices_df (verfügbar: {list(prices_filtered.columns)})"
        )

    if len(prices_filtered) < 30:
        raise ValueError(
            f"Zu wenig Preisdaten für '{coin}': {len(prices_filtered)} Zeilen (min 30 erforderlich)"
        )

    close_all = prices_filtered  # Alle Coins für Layer 1
    close = prices_filtered[coin]  # Einzelner Coin für Layer 2

    # ── Layer 1: Cross-Sectional Momentum + On-Chain Health ───────────────────
    momentum_df = cross_sectional_momentum(close_all)
    if coin in momentum_df.index:
        momentum_rank = float(momentum_df.loc[coin, "composite_rank"])
    else:
        momentum_rank = float(len(close_all.columns) / 2)  # Mittelrang als Fallback

    if onchain_df is not None and len(onchain_df) > 0:
        # Filtere On-Chain-Daten auf asof
        if "date" in onchain_df.columns:
            onchain_filtered = onchain_df[pd.to_datetime(onchain_df["date"]) <= asof_ts]
        else:
            onchain_filtered = onchain_df
        if len(onchain_filtered) > 0:
            health_scores = onchain_health_score(onchain_filtered)
            onchain_score = float(health_scores.get(coin, 0.5))
        else:
            onchain_score = 0.5
    else:
        onchain_score = 0.5

    # ── Layer 2: Technische Indikatoren + Consensus-Vote ─────────────────────
    # SMA(100): Close über 100-Tage-Durchschnitt
    sma_100 = sma(close, window=100)
    # RSI(14): Relative Stärke
    rsi_14 = rsi(close, window=14)
    # MACD: Momentum-Divergenz
    _macd_line, _signal_line, macd_hist = macd(close)

    # Binäre Signale (0 oder 1) — letzter verfügbarer Wert
    last_close = float(close.iloc[-1])
    last_sma = sma_100.iloc[-1]
    last_rsi = rsi_14.iloc[-1]
    last_macd_hist = macd_hist.iloc[-1]

    # Signale: 1 wenn bullisch, 0 wenn bearisch oder nicht verfügbar
    ma_signal = 1 if (not np.isnan(last_sma) and last_close > last_sma) else 0
    rsi_signal = 1 if (not np.isnan(last_rsi) and last_rsi > 50) else 0
    macd_signal = 1 if (not np.isnan(last_macd_hist) and last_macd_hist > 0) else 0

    # Consensus-Vote: 2-of-3 Mehrheitsregel
    signals_df = pd.DataFrame(
        {
            "ma_signal": [ma_signal],
            "rsi_signal": [rsi_signal],
            "macd_signal": [macd_signal],
        }
    )
    consensus_result = int(consensus_vote(signals_df).iloc[0])

    # Anzahl der aktiven Signale für Consensus-String
    n_active = ma_signal + rsi_signal + macd_signal
    consensus_str = f"{n_active}/{_N_SIGNALS}"

    # ── Aktion bestimmen (Layer 1 + 2 kombiniert) ────────────────────────────
    n_coins = len(close_all.columns)
    sell_threshold = max(int(n_coins * 0.8), _SELL_RANK_THRESHOLD)

    if consensus_result == 1:
        action = "BUY"
    elif momentum_rank > sell_threshold:
        action = "SELL"
    else:
        action = "HOLD"

    # ── Layer 3: Vol-Forecast + Sizing ───────────────────────────────────────
    if vol_model_info is not None:
        try:
            pred_vol_value = predict_vol(close, vol_model_info, asof)
        except Exception:  # noqa: BLE001
            logger.warning("predict_vol fehlgeschlagen für %s, Fallback 0.60", coin)
            pred_vol_value = 0.60
    else:
        pred_vol_value = 0.60

    size_factor = apply_sizing(action, pred_vol_value)

    # ── Confidence berechnen (Anteil aktiver Signale) ────────────────────────
    # 0 = alle gegen, 0.33 = 1/3, 0.67 = 2/3, 1.0 = 3/3
    confidence = float(n_active) / _N_SIGNALS

    # ── SignalVector zusammenbauen ────────────────────────────────────────────
    sub_scores: dict[str, float] = {
        "ma_signal": float(ma_signal),
        "macd_signal": float(macd_signal),
        "rsi_signal": float(rsi_signal),
        "vol_pred": float(pred_vol_value),
        "momentum_rank": float(momentum_rank),
        "onchain_score": float(onchain_score),
    }

    return SignalVector(
        coin=coin,
        asof=asof,
        action=action,  # type: ignore[arg-type]
        size_factor=size_factor,
        consensus=consensus_str,
        sub_scores=sub_scores,
        confidence=confidence,
    )
