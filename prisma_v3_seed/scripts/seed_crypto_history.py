"""Bootstrap-Seed: Krypto OHLCV -> crypto_price_history.

Quelle: CryptoDataDownload CSV (gratis, kein Rate-Limit, seit 2017).
  daily: https://www.cryptodatadownload.com/cdd/Binance_{PAIR}_d.csv
  1h:    https://www.cryptodatadownload.com/cdd/Binance_{PAIR}_1h.csv
CSV-Header-Zeile 1 ist ein Disclaimer -> skiprows=1.

Aufruf:  uv run python scripts/seed_crypto_history.py --from 2017-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import pandas as pd

from backend.application.pipeline.etl import normalize_crypto_ohlcv, validate_ohlcv
from backend.application.pipeline.load import bulk_upsert

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed_crypto")

# Nur Coins (keine ETP/ETF — Constraint Kap. 14.6).
PAIRS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
         "ADA": "ADAUSDT", "BNB": "BNBUSDT", "XRP": "XRPUSDT"}
_CDD = "https://www.cryptodatadownload.com/cdd/Binance_{pair}_{tf}.csv"


def _fetch_csv(pair: str, tf: str) -> pd.DataFrame:
    url = _CDD.format(pair=pair, tf=tf)
    df = pd.read_csv(url, skiprows=1)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="mixed", utc=True)
    df = df.set_index("date").sort_index()
    # Volume-Spalte heisst je nach File 'volume usdt' / 'volume btc' -> erste 'volume*'
    vol = next((c for c in df.columns if c.startswith("volume")), None)
    if vol:
        df["volume"] = df[vol]
    return df[["open", "high", "low", "close", "volume"]]


async def seed_one(ticker: str, pair: str, tf_label: str, tf_url: str, start: str) -> int:
    df = _fetch_csv(pair, tf_url)
    df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if df.empty:
        log.warning("%s %s: leer", ticker, tf_label)
        return 0
    rows = normalize_crypto_ohlcv(df, ticker=ticker, interval=tf_label,
                                  source="cryptodatadownload")
    clean, _ = validate_ohlcv(rows, table="crypto_price_history")
    return await bulk_upsert("crypto_price_history", clean)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2017-01-01")
    ap.add_argument("--hourly-from", dest="hourly_start", default="2020-01-01")
    args = ap.parse_args()

    total = 0
    for ticker, pair in PAIRS.items():
        try:
            total += await seed_one(ticker, pair, "1d", "d", args.start)
            # 1h nur für BTC/ETH (Intraday-Agent) — andere zu gross/unnötig
            if ticker in ("BTC", "ETH"):
                total += await seed_one(ticker, pair, "1h", "1h", args.hourly_start)
        except Exception as e:  # noqa: BLE001
            log.error("%s fehlgeschlagen: %s", ticker, e)
    log.info("FERTIG seed_crypto_history: %d Zeilen", total)


if __name__ == "__main__":
    asyncio.run(main())
