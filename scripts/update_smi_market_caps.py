#!/usr/bin/env python3
"""Aktualisiert market_cap_chf für alle 20 SMI-Stocks aus yfinance.

Läuft standalone. Setzt DATABASE_URL aus der Umgebung voraus.
Idempotent: überschreibt bestehende Werte, löscht nichts.

Usage:
    python scripts/update_smi_market_caps.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.domain.errors import SwissDataUnavailableError
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

SMI_TICKERS = [
    "NESN",
    "NOVN",
    "ROG",
    "ABBN",
    "ZURN",
    "UBSG",
    "UHR",
    "GEBN",
    "GIVN",
    "LONN",
    "SREN",
    "SGKN",
    "SLHN",
    "SCMN",
    "BALN",
    "HOLN",
    "PGHN",
    "KRIN",
    "CFR",
    "STMN",
]


async def update(session: AsyncSession) -> None:
    adapter = YFinanceSwissAdapter()
    success = 0
    skipped = 0

    for ticker in SMI_TICKERS:
        try:
            fundamentals = await adapter.get_fundamentals(ticker)
            await session.execute(
                text("""
                    UPDATE stocks
                    SET market_cap_chf = :market_cap_chf
                    WHERE ticker = :ticker
                """),
                {
                    "market_cap_chf": float(fundamentals.market_cap_chf)
                    if fundamentals.market_cap_chf is not None
                    else None,
                    "ticker": ticker,
                },
            )
            _logger.info("✓ %s — market_cap_chf aktualisiert", ticker)
            success += 1
        except SwissDataUnavailableError:
            _logger.warning("⚠ %s — kein yfinance-Datensatz, übersprungen", ticker)
            skipped += 1
        except Exception as exc:
            _logger.error("✗ %s — Fehler: %s", ticker, exc)
            skipped += 1

    await session.commit()
    _logger.info("Update abgeschlossen: %d aktualisiert, %d übersprungen.", success, skipped)


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _logger.error("DATABASE_URL nicht gesetzt")
        sys.exit(1)

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        await update(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
