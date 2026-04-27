"""Seed-Script: legt das Demo-Universum "Demo-US-5" mit 5 US-Stocks an.

Idempotent — kann mehrfach ausgeführt werden ohne Duplikate.
Datenquelle: Hardcoded-Fixture (ADR-0005: yfinance + FMP als Laufzeit-Quelle folgt).

Verwendung:
    python scripts/seed_demo_universe.py
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_demo_universe.py
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

# Repo-Root auf sys.path, damit backend-Imports funktionieren.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.infrastructure.persistence.models.stock import StockORM
from backend.infrastructure.persistence.models.universe import UniverseORM

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://prisma:prisma@localhost:5432/prisma",
)

STOCKS = [
    {"ticker": "AAPL",  "name": "Apple Inc.",          "isin": "US0378331005", "sector": "Technology",       "country": "US", "currency": "USD"},
    {"ticker": "MSFT",  "name": "Microsoft Corp.",      "isin": "US5949181045", "sector": "Technology",       "country": "US", "currency": "USD"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.",        "isin": "US02079K3059", "sector": "Communication",    "country": "US", "currency": "USD"},
    {"ticker": "NVDA",  "name": "NVIDIA Corp.",         "isin": "US67066G1040", "sector": "Technology",       "country": "US", "currency": "USD"},
    {"ticker": "JPM",   "name": "JPMorgan Chase & Co.", "isin": "US46625H1005", "sector": "Financial",        "country": "US", "currency": "USD"},
]

UNIVERSE_NAME = "Demo-US-5"
UNIVERSE_REGION = "US"


async def seed(session: AsyncSession) -> None:
    seeded_stocks = 0
    for data in STOCKS:
        exists = await session.execute(
            select(StockORM).where(StockORM.ticker == data["ticker"])
        )
        if exists.scalar_one_or_none() is None:
            session.add(StockORM(id=uuid.uuid4(), **data))
            seeded_stocks += 1

    universe_exists = await session.execute(
        select(UniverseORM).where(UniverseORM.name == UNIVERSE_NAME)
    )
    seeded_universe = 0
    if universe_exists.scalar_one_or_none() is None:
        session.add(UniverseORM(
            id=uuid.uuid4(),
            name=UNIVERSE_NAME,
            region=UNIVERSE_REGION,
            tickers=[s["ticker"] for s in STOCKS],
        ))
        seeded_universe = 1

    await session.commit()
    print(f"Stocks neu: {seeded_stocks} (übersprungen: {len(STOCKS) - seeded_stocks})")
    print(f"Universe '{UNIVERSE_NAME}': {'angelegt' if seeded_universe else 'bereits vorhanden'}")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
