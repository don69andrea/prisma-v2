"""Extract / Normalize / Validate — Helfer für die Seed-Skripte.

Trennt die drei ETL-Phasen sauber, damit jede Quelle (yfinance, CSV, API)
denselben Validierungs- und Lade-Pfad nutzt. Geladen wird über pipeline.load.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

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


def normalize_ohlcv(df: pd.DataFrame, *, ticker: str, source: str, currency: str) -> list[dict]:
    """Vereinheitlicht ein OHLCV-DataFrame (yfinance/CSV) auf das DB-Schema
    von stock_price_history. Erwartet Spalten Open/High/Low/Close/Volume und
    einen DatetimeIndex (daily)."""
    df = df.rename(columns=str.lower)
    out = []
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
) -> list[dict]:
    df = df.rename(columns=str.lower)
    out = []
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
    rows: list[dict], *, table: str, spike_pct: float = 0.25
) -> tuple[list[dict], ValidationReport]:
    """Wirft kaputte Zeilen raus (NULL/negativ in OHLC, high<low) und meldet
    Preis-Spikes & Datumslücken. WICHTIG: meldet laut statt still zu droppen."""
    clean, dropped, spikes, gaps = [], 0, [], []
    prev_close = None
    for r in rows:
        o, h, low, c = r.get("open"), r.get("high"), r.get("low"), r.get("close")
        if None in (o, h, low, c) or min(o, h, low, c) <= 0 or h < low:
            dropped += 1
            continue
        if prev_close is not None and abs(c - prev_close) / prev_close > spike_pct:
            spikes.append(
                f"{r['ticker']} {r.get('date') or r.get('timestamp')}: {prev_close:.2f}->{c:.2f}"
            )
        clean.append(r)
        prev_close = c
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
