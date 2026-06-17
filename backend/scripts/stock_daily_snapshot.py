#!/usr/bin/env python3
"""Swiss Stock Daily Snapshot — läuft täglich via Render Cron.

Berechnet SignalAggregationService-Signale für alle SMI20-Titel
und persistiert sie in stock_daily_signals.
"""

from __future__ import annotations

import asyncio
import logging

from backend.application.services.signal_aggregation_service import SignalAggregationService
from backend.domain.models.stock_signal_record import StockSignalRecord
from backend.infrastructure.persistence.repositories.stock_signal_repository import (
    SQLAStockSignalRepository,
)
from backend.infrastructure.persistence.session import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stock_daily_snapshot")

_SMI20 = [
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
    "SIKA",
    "HOLN",
    "PGHN",
    "KNIN",
    "CFR",
    "STMN",
]


async def main() -> None:
    log.info("=== Stock Daily Snapshot gestartet ===")
    scoring_svc = SignalAggregationService()

    try:
        signals = await scoring_svc.get_signals(_SMI20)
    except Exception:
        log.exception("get_signals() fehlgeschlagen")
        return

    session_factory = get_session_factory()
    saved = 0
    async with session_factory() as session:
        repo = SQLAStockSignalRepository(session)
        for signal in signals:
            try:
                record = StockSignalRecord(
                    id="",  # Repository generiert UUID
                    ticker=signal.ticker,
                    snapshot_date=signal.snapshot_date,
                    signal=signal.signal,
                    weighted_score=signal.weighted_score,
                    quant_score=signal.quant_score,
                    ml_score=signal.ml_score,
                    macro_score=signal.macro_score,
                    confidence=signal.confidence,
                    is_3a_eligible=signal.is_3a_eligible,
                )
                await repo.save(record)
                saved += 1
                log.info("  OK %s: %s (%.1f)", signal.ticker, signal.signal, signal.weighted_score)
            except Exception:
                log.exception("  FEHLER bei %s", signal.ticker)
        await session.commit()

    log.info("=== Snapshot fertig: %d/%d gespeichert ===", saved, len(signals))


if __name__ == "__main__":
    asyncio.run(main())
