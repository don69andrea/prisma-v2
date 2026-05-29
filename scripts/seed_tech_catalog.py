"""Seed-Script: erweitert den Stock-Katalog um Tech-Heavy-Stocks für Demo.

Legt 6 zusätzliche Tech-Stocks (META, NFLX, AMD, INTC, ORCL, CRM) +
ein 'Tech-Big-12' Universe an. Idempotent — mehrfach ausführbar.

Voraussetzung: stub_fundamentals.py muss bereits Demo-Daten für diese
Tickers enthalten (siehe backend/infrastructure/providers/stub_fundamentals.py).

Verwendung:
    DATABASE_URL=postgresql+asyncpg://prisma:prisma@localhost:5432/prisma \\
        python scripts/seed_tech_catalog.py
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.infrastructure.persistence.models.stock import StockORM
from backend.infrastructure.persistence.models.universe import UniverseORM

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://prisma:prisma@localhost:5432/prisma",
)

# Neue Stocks, die noch nicht im Katalog sind (META, NFLX, AMD, INTC, ORCL, CRM).
# AAPL/MSFT/GOOGL/NVDA/AMZN/TSLA sind bereits via seed_demo_universe.py oder
# Migration 0009b angelegt.
NEW_STOCKS = [
    {
        "ticker": "META",
        "name": "Meta Platforms Inc.",
        "isin": "US30303M1027",
        "sector": "Communication",
        "country": "US",
        "currency": "USD",
    },
    {
        "ticker": "NFLX",
        "name": "Netflix Inc.",
        "isin": "US64110L1061",
        "sector": "Communication",
        "country": "US",
        "currency": "USD",
    },
    {
        "ticker": "AMD",
        "name": "Advanced Micro Devices Inc.",
        "isin": "US0079031078",
        "sector": "Technology",
        "country": "US",
        "currency": "USD",
    },
    {
        "ticker": "INTC",
        "name": "Intel Corp.",
        "isin": "US4581401001",
        "sector": "Technology",
        "country": "US",
        "currency": "USD",
    },
    {
        "ticker": "ORCL",
        "name": "Oracle Corp.",
        "isin": "US68389X1054",
        "sector": "Technology",
        "country": "US",
        "currency": "USD",
    },
    {
        "ticker": "CRM",
        "name": "Salesforce Inc.",
        "isin": "US79466L3024",
        "sector": "Technology",
        "country": "US",
        "currency": "USD",
    },
]

# Tech-Big-12 = alle 12 Tech-relevanten Tickers im erweiterten Katalog.
TECH_BIG_12 = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "NVDA",
    "AMZN",
    "TSLA",  # existing
    "META",
    "NFLX",
    "AMD",
    "INTC",
    "ORCL",
    "CRM",  # new
]

UNIVERSE_NAME = "Tech-Big-12"
UNIVERSE_REGION = "US"


async def seed(session: AsyncSession) -> None:
    seeded_stocks = 0
    for data in NEW_STOCKS:
        exists = await session.execute(select(StockORM).where(StockORM.ticker == data["ticker"]))
        if exists.scalar_one_or_none() is None:
            session.add(StockORM(id=uuid.uuid4(), **data))
            seeded_stocks += 1

    universe_exists = await session.execute(
        select(UniverseORM).where(UniverseORM.name == UNIVERSE_NAME)
    )
    seeded_universe = 0
    if universe_exists.scalar_one_or_none() is None:
        session.add(
            UniverseORM(
                id=uuid.uuid4(),
                name=UNIVERSE_NAME,
                region=UNIVERSE_REGION,
                tickers=TECH_BIG_12,
            )
        )
        seeded_universe = 1

    await session.commit()
    print(f"Stocks neu: {seeded_stocks} (übersprungen: {len(NEW_STOCKS) - seeded_stocks})")
    print(f"Universe '{UNIVERSE_NAME}': {'angelegt' if seeded_universe else 'bereits vorhanden'}")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
