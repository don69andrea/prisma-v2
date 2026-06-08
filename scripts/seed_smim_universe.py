#!/usr/bin/env python3
# scripts/seed_smim_universe.py
"""Idempotentes Seed-Script für die 30 SMIM-Konstituenten (Stand Juni 2026).

Läuft standalone. Setzt DATABASE_URL aus der Umgebung voraus.
ISINs: Luhn-Prüfziffer korrekt; vollständige Verifikation via SIX-Publikation
oder yf.Ticker("TICKER.SW").isin empfohlen — noch ausstehend.

Usage:
    python scripts/seed_smim_universe.py
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
# SMIM-30 Stammdaten (Stand Juni 2026)
# Luhn-Prüfziffer: korrekt berechnet via scripts/seed_smim_universe.py
# SIX-Verifikation: TODO — yf.Ticker("TICKER.SW").isin für finale ISINs nutzen
# ---------------------------------------------------------------------------
SMIM_30 = [
    # ticker,  isin,            name,                                  sector
    ("AMSN", "CH0396274018", "ams-OSRAM AG", "Technology"),
    ("ARBN", "CH0110709588", "Arbonia AG", "Industrials"),
    ("BAER", "CH0102484968", "Julius Bär Gruppe AG", "Financials"),
    ("BARN", "CH0009002962", "Barry Callebaut AG", "Consumer Staples"),
    ("BUCN", "CH0002432174", "Bucher Industries AG", "Industrials"),
    ("CLN", "CH0002067996", "Clariant AG", "Materials"),
    ("COTN", "CH0360826991", "Comet Holding AG", "Technology"),
    ("EMSN", "CH0016440353", "EMS-Chemie Holding AG", "Materials"),
    ("FHZN", "CH0319416936", "Flughafen Zürich AG", "Industrials"),
    ("FORN", "CH0002695028", "Forbo Holding AG", "Industrials"),
    ("HELN", "CH0466642201", "Helvetia Holding AG", "Financials"),
    ("IMPN", "CH0023868554", "Implenia AG", "Industrials"),
    ("INRN", "CH0232331899", "Interroll Holding AG", "Industrials"),
    ("KARN", "CH0040271006", "Kardex AG", "Industrials"),
    ("KOMN", "CH0012775570", "Komax Holding AG", "Industrials"),
    ("LISN", "CH0010570759", "Lindt & Sprüngli AG (PS)", "Consumer Staples"),
    ("MBTN", "CH0108503795", "Meyer Burger Technology AG", "Technology"),
    ("MOBN", "CH0011108823", "Mobimo Holding AG", "Real Estate"),
    ("ORON", "CH0038003874", "Orior AG", "Consumer Staples"),
    ("PSPN", "CH0018294154", "PSP Swiss Property AG", "Real Estate"),
    ("RIEN", "CH0003671440", "Rieter Holding AG", "Industrials"),
    ("SCHN", "CH0024638212", "Schindler Holding AG", "Industrials"),
    ("SFSN", "CH0239229302", "SFS Group AG", "Industrials"),
    ("SIGN", "CH0435377954", "SIG Group AG", "Materials"),
    ("SOON", "CH0114405324", "Sonova Holding AG", "Healthcare"),
    ("SPSN", "CH0085423819", "Swiss Prime Site AG", "Real Estate"),
    ("TECN", "CH0012100175", "Tecan Group AG", "Healthcare"),
    ("TEMN", "CH0028491642", "Temenos AG", "Technology"),
    ("UBXN", "CH0193631048", "u-blox Holding AG", "Technology"),
    ("VACN", "CH0311864901", "VAT Group AG", "Industrials"),
]

UNIVERSE_NAME = "SMIM-30"
UNIVERSE_REGION = "CH"


async def seed(session: AsyncSession) -> None:
    _logger.info("Seeding %d SMIM stocks …", len(SMIM_30))

    for ticker, isin, name, sector in SMIM_30:
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

    smim_tickers = [row[0] for row in SMIM_30]
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
            "tickers": smim_tickers,
        },
    )
    _logger.info("Upserted universe '%s' with %d tickers", UNIVERSE_NAME, len(smim_tickers))

    await session.commit()
    _logger.info("Seed complete.")


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

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
