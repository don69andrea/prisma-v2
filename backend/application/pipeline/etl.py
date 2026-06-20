"""Extract / Normalize / Validate — Helfer für die Seed-Skripte.

Trennt die drei ETL-Phasen sauber, damit jede Quelle (yfinance, CSV, API)
denselben Validierungs- und Lade-Pfad nutzt. Geladen wird über pipeline.load.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    table: str
    rows_in: int
    rows_out: int
    dropped: int
    gaps: list[str] = field(default_factory=list)
    spikes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # >5% verworfen oder >0 Spikes => manueller Blick nötig, aber kein harter Abbruch
        return self.rows_out > 0


# --- NORMALIZE ------------------------------------------------------------


def normalize_ohlcv(
    df: pd.DataFrame, *, ticker: str, source: str, currency: str
) -> list[dict[str, Any]]:
    """Vereinheitlicht ein OHLCV-DataFrame (yfinance/CSV) auf das DB-Schema
    von stock_price_history. Erwartet Spalten Open/High/Low/Close/Volume und
    einen DatetimeIndex (daily)."""
    df = df.rename(columns=str.lower)
    out: list[dict[str, Any]] = []
    for ts, r in df.iterrows():
        out.append(
            {
                "ticker": ticker,
                "date": pd.Timestamp(ts).date(),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(r["volume"]) if pd.notna(r.get("volume")) else None,
                "currency": currency,
                "source": source,
            }
        )
    return out


def normalize_crypto_ohlcv(
    df: pd.DataFrame, *, ticker: str, interval: str, source: str, currency: str = "USD"
) -> list[dict[str, Any]]:
    df = df.rename(columns=str.lower)
    out: list[dict[str, Any]] = []
    for ts, r in df.iterrows():
        out.append(
            {
                "ticker": ticker,
                "timestamp": pd.Timestamp(ts).to_pydatetime(),
                "interval": interval,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]) if pd.notna(r.get("volume")) else None,
                "currency": currency,
                "source": source,
            }
        )
    return out


# --- VALIDATE -------------------------------------------------------------


def validate_ohlcv(
    rows: list[dict[str, Any]], *, table: str, spike_pct: float = 0.25
) -> tuple[list[dict[str, Any]], ValidationReport]:
    """Wirft kaputte Zeilen raus (NULL/negativ in OHLC, high<low) und meldet
    Preis-Spikes & Datumslücken. WICHTIG: meldet laut statt still zu droppen."""
    clean: list[dict[str, Any]] = []
    dropped = 0
    spikes: list[str] = []
    gaps: list[str] = []
    prev_close: float | None = None
    for r in rows:
        o: Any = r.get("open")
        h: Any = r.get("high")
        low: Any = r.get("low")
        c: Any = r.get("close")
        if None in (o, h, low, c):
            dropped += 1
            continue
        o_f, h_f, low_f, c_f = float(o), float(h), float(low), float(c)
        if min(o_f, h_f, low_f, c_f) <= 0 or h_f < low_f:
            dropped += 1
            continue
        if prev_close is not None and abs(c_f - prev_close) / prev_close > spike_pct:
            spikes.append(
                f"{r['ticker']} {r.get('date') or r.get('timestamp')}: {prev_close:.2f}->{c_f:.2f}"
            )
        clean.append(r)
        prev_close = c_f
    rep = ValidationReport(
        table=table,
        rows_in=len(rows),
        rows_out=len(clean),
        dropped=dropped,
        spikes=spikes,
        gaps=gaps,
    )
    if dropped:
        log.warning("validate %s: %d Zeilen verworfen (von %d)", table, dropped, len(rows))
    if spikes:
        log.warning(
            "validate %s: %d Preis-Spikes >%.0f%%: %s",
            table,
            len(spikes),
            spike_pct * 100,
            spikes[:5],
        )
    return clean, rep
