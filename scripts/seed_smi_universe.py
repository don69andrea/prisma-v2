#!/usr/bin/env python3
# scripts/seed_smi_universe.py
"""Idempotentes Seed-Script für die 20 SMI-Konstituenten (Stand Juni 2026).

Läuft standalone. Setzt DATABASE_URL aus der Umgebung voraus.
Alle ISINs MÜSSEN via SIX-Publikation oder yfinance vor dem ersten
Commit verifiziert werden (mit * markierte sind Platzhalter).

Usage:
    python scripts/seed_smi_universe.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SMI-20 Stammdaten (Stand Juni 2026)
# ISIN-Verifikation via: yf.Ticker("TICKER.SW").isin oder SIX-Publikation
# ---------------------------------------------------------------------------
SMI_20 = [
    # ticker, isin, name, sector
    ("NESN",  "CH0038863350", "Nestlé SA",                          "Consumer Staples"),
    ("NOVN",  "CH0012221716", "Novartis AG",                        "Healthcare"),       # * verify
    ("ROG",   "CH0012032048", "Roche Holding AG",                   "Healthcare"),       # * verify
    ("ABBN",  "CH0012221716", "ABB Ltd",                            "Industrials"),      # * verify
    ("ZURN",  "CH0011075394", "Zurich Insurance Group AG",          "Financials"),       # * verify
    ("UBSG",  "CH0244767585", "UBS Group AG",                       "Financials"),       # * verify
    ("UHR",   "CH0012255151", "The Swatch Group AG",                "Consumer Disc."),   # * verify
    ("GEBN",  "CH0030170408", "Geberit AG",                         "Industrials"),      # * verify
    ("GIVN",  "CH0010645932", "Givaudan SA",                        "Materials"),        # * verify
    ("LONN",  "CH0013841017", "Lonza Group AG",                     "Healthcare"),       # * verify
    ("SREN",  "CH0126881561", "Swiss Re AG",                        "Financials"),       # * verify
    ("SGKN",  "CH0002497458", "SGS SA",                             "Industrials"),      # * verify
    ("SLHN",  "CH0014852781", "Swiss Life Holding AG",              "Financials"),       # * verify
    ("SCMN",  "CH0008742519", "Swisscom AG",                        "Communication"),    # * verify
    ("BALN",  "CH0012221716", "Baloise Holding AG",                 "Financials"),       # * verify
    ("HOLN",  "CH0012214059", "Holcim AG",                          "Materials"),        # * verify
    ("PGHN",  "CH0024608827", "Partners Group Holding AG",          "Financials"),       # * verify
    ("KRIN",  "CH0334776754", "Kühne + Nagel International AG",     "Industrials"),      # * verify
    ("CFR",   "CH0210483332", "Compagnie Financière Richemont SA",  "Consumer Disc."),   # * verify
    ("STMN",  "CH0012050267", "Straumann Holding AG",               "Healthcare"),       # * verify via yf.Ticker("STMN.SW").isin
]

UNIVERSE_NAME = "SMI-20"
UNIVERSE_REGION = "CH"


async def seed(session: AsyncSession) -> None:
    _logger.info("Seeding %d SMI stocks …", len(SMI_20))

    for ticker, isin, name, sector in SMI_20:
        await session.execute(
            text("""
                INSERT INTO stocks (id, ticker, isin, name, sector, country, currency, exchange)
                VALUES (:id, :ticker, :isin, :name, :sector, 'CH', 'CHF', 'XSWX')
                ON CONFLICT (ticker) DO UPDATE SET
                    isin     = EXCLUDED.isin,
                    name     = EXCLUDED.name,
                    sector   = EXCLUDED.sector,
                    country  = EXCLUDED.country,
                    currency = EXCLUDED.currency,
                    exchange = EXCLUDED.exchange
            """),
            {
                "id": str(uuid.uuid4()),
                "ticker": ticker,
                "isin": isin,
                "name": name,
                "sector": sector,
            },
        )
        _logger.info("  ✓ %s (%s)", ticker, name)

    # Upsert SMI-20 Universe entry (tickers stored as ARRAY column per schema)
    smi_tickers = [row[0] for row in SMI_20]
    await session.execute(
        text("""
            INSERT INTO universes (id, name, region, tickers)
            VALUES (:id, :name, :region, :tickers)
            ON CONFLICT (name) DO UPDATE SET
                region  = EXCLUDED.region,
                tickers = EXCLUDED.tickers
        """),
        {
            "id": str(uuid.uuid4()),
            "name": UNIVERSE_NAME,
            "region": UNIVERSE_REGION,
            "tickers": smi_tickers,
        },
    )
    _logger.info("Upserted universe '%s' with %d tickers", UNIVERSE_NAME, len(smi_tickers))

    await session.commit()
    _logger.info("Seed complete.")


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    # asyncpg requires postgresql+asyncpg:// prefix
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
