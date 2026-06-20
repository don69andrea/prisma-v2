"""Bootstrap-Seed: CH-Aktien Tagespreise -> stock_price_history.

Quelle: yfinance Bulk (gratis, .SW-Titel, GH-Action-IPs nicht geblockt).
Idempotent — mehrfach ausführbar. Bei Yahoo-Blockade einzelner Titel:
loggen und weiter (kein Abbruch).

Aufruf:  uv run python scripts/seed_historical_prices.py --from 2015-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import yfinance as yf

from backend.application.pipeline.etl import normalize_ohlcv, validate_ohlcv
from backend.application.pipeline.load import bulk_upsert

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed_prices")

# SMI-20 + SMIM-Auswahl. Sollte langfristig aus index_constituents (CHALLENGE 04 /
# PIT-Universum) kommen, inkl. delisteter Titel wie CSGN.
SMI = [
    "NESN",
    "NOVN",
    "ROG",
    "UBSG",
    "ZURN",
    "ABBN",
    "LONN",
    "SIKA",
    "GIVN",
    "CFR",
    "ALC",
    "HOLN",
    "SLHN",
    "GEBN",
    "SCMN",
    "SOON",
    "LOGN",
    "PGHN",
    "SREN",
    "BAER",
]


def _yf(ticker: str) -> str:
    return f"{ticker}.SW"


async def seed_one(ticker: str, start: str) -> int:
    df = yf.download(_yf(ticker), start=start, interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        log.warning("%s: keine Daten von yfinance", ticker)
        return 0
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    rows = normalize_ohlcv(df, ticker=ticker, source="yfinance", currency="CHF")
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    return await bulk_upsert("stock_price_history", clean)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2015-01-01")
    ap.add_argument("--tickers", nargs="*", default=SMI)
    args = ap.parse_args()

    total = 0
    for t in args.tickers:
        try:
            total += await seed_one(t, args.start)
        except Exception as e:  # noqa: BLE001 — Seed soll bei Einzelfehler weiterlaufen
            log.error("%s fehlgeschlagen: %s", t, e)
    log.info("FERTIG seed_historical_prices: %d Zeilen, %d Titel", total, len(args.tickers))


if __name__ == "__main__":
    asyncio.run(main())
