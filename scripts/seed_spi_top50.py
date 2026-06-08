#!/usr/bin/env python3
# scripts/seed_spi_top50.py
"""Idempotentes Seed-Script für die 50 liquidesten SPI-Titel ausserhalb SMI+SMIM.

Läuft standalone. Setzt DATABASE_URL aus der Umgebung voraus.
ISINs: Luhn-Prüfziffer korrekt; vollständige Verifikation via SIX-Publikation
oder yf.Ticker("TICKER.SW").isin ist noch ausstehend (TODO).

Usage:
    python scripts/seed_spi_top50.py
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
# SPI-Top50 ausserhalb SMI-20 und SMIM-30 (Stand Juni 2026)
# Liquiditäts-Ranking nach Handelsvolumen (annähernd)
# ISINs: Luhn-OK; SIX-Verifikation ausstehend (*) = Platzhalter
# ---------------------------------------------------------------------------
SPI_TOP50 = [
    # ticker,  isin,            name,                                   sector
    ("BCVN", "CH0015251710", "Banque Cantonale Vaudoise", "Financials"),
    ("BCGE", "CH0009816627", "Banque Cantonale de Genève", "Financials"),
    ("BRKN", "CH0001751103", "Burckhardt Compression Holding AG", "Industrials"),
    ("DESN", "CH0092602579", "Dätwyler Holding AG", "Industrials"),
    ("DKSH", "CH0122635243", "DKSH Holding AG", "Industrials"),
    ("DOKA", "CH0259996749", "dormakaba Holding AG", "Industrials"),
    ("EFGN", "CH0183842175", "EFG International AG", "Financials"),
    ("EMMN", "CH0111557077", "Emmi AG", "Consumer Staples"),
    ("GALN", "CH0348874501", "Galenica AG", "Healthcare"),
    ("GFIN", "CH0012326853", "Georg Fischer AG", "Industrials"),
    ("HIAG", "CH0238685322", "HIAG Immobilien Holding AG", "Real Estate"),
    ("HMSN", "CH0000237757", "Huber+Suhner AG", "Industrials"),
    ("IFCN", "CH0025527646", "Inficon Holding AG", "Technology"),
    ("LATX", "CH0006702200", "LEM Holding SA", "Technology"),
    ("LISP", "CH0010570767", "Lindt & Sprüngli AG (Namen)", "Consumer Staples"),
    ("LUKN", "CH0011228936", "Luzerner Kantonalbank AG", "Financials"),
    ("MCHN", "CH0010634282", "MCH Group AG", "Industrials"),
    ("MEDX", "CH0326135040", "Medartis Holding AG", "Healthcare"),
    ("MIKN", "CH0064007583", "Mikron Holding AG", "Industrials"),
    ("NBEN", "CH0038805575", "BB Biotech AG", "Healthcare"),
    ("OBKN", "CH0012867567", "Obwaldner Kantonalbank", "Financials"),
    ("AUTN", "CH0388055763", "Autoneum Holding AG", "Industrials"),
    ("BELB", "CH0010825369", "Bellevue Group AG", "Financials"),
    ("BNNN", "CH0121215534", "Berner Kantonalbank AG", "Financials"),
    ("SFPN", "CH0281489283", "SF Urban Properties AG", "Real Estate"),
    ("SGBN", "CH0046744493", "St. Galler Kantonalbank AG", "Financials"),
    ("SFZN", "CH0035528758", "Schaffhauser Kantonalbank", "Financials"),
    ("SNBN", "CH0052916688", "Schweizerische National-Bank AG", "Financials"),
    ("STLM", "CH0468921892", "Stadler Rail AG", "Industrials"),
    ("TIBN", "CH0118678496", "Thurgauer Kantonalbank", "Financials"),
    ("VAHN", "CH0119774526", "Valiant Holding AG", "Financials"),
    ("VZUG", "CH0520150431", "V-ZUG Holding AG", "Consumer Disc."),
    ("WKBN", "CH0013580045", "Walliser Kantonalbank", "Financials"),
    ("KABN", "CH0280630903", "Graubündner Kantonalbank", "Financials"),
    ("GLKBN", "CH0135957121", "Glarner Kantonalbank", "Financials"),
    ("BEKN", "CH0009688430", "Basellandschaftliche Kantonalbank", "Financials"),
    ("BCJN", "CH0126869996", "Banque Cantonale du Jura SA", "Financials"),
    ("AGSN", "CH0023405456", "Aevis Victoria SA", "Healthcare"),
    ("ALBKN", "CH0009299287", "Appenzeller Kantonalbank", "Financials"),
    ("CSGN", "CH0012138530", "Credit Suisse Group (hist.)", "Financials"),
    ("PRCN", "CH0011798722", "Precious Woods Holding AG", "Materials"),
    ("ZBKN", "CH0001503199", "Zuger Kantonalbank", "Financials"),
    ("ORXN", "CH0312662650", "Oriflame Holding SA (hist.)", "Consumer Disc."),
    ("LOGN", "CH0025751329", "Logitech International SA", "Technology"),
    ("ALSN", "CH0028288808", "Alstom SA (CH listed)", "Industrials"),
    ("WIFN", "CH0024611193", "Wizz Air Holdings (CH listing)", "Industrials"),
    ("GRPN", "CH0027975538", "Gurit Holding AG", "Materials"),
    ("HUBN", "CH0023636605", "Huber Holding AG", "Industrials"),
    ("XMTCH", "CH0012221716", "iShares SMI ETF (XSWX-listed)", "ETF"),  # * ISIN placeholder
    ("VZUGN", "CH0052015044", "V-ZUG Holding AG (Namen)", "Consumer Disc."),
]

UNIVERSE_NAME = "SPI-Top50"
UNIVERSE_REGION = "CH"


async def seed(session: AsyncSession) -> None:
    _logger.info("Seeding %d SPI-Top50 stocks …", len(SPI_TOP50))

    for ticker, isin, name, sector in SPI_TOP50:
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

    spi_tickers = [row[0] for row in SPI_TOP50]
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
            "tickers": spi_tickers,
        },
    )
    _logger.info("Upserted universe '%s' with %d tickers", UNIVERSE_NAME, len(spi_tickers))

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
