"""Bootstrap-Seed: PIT-Universum (SMI/SMIM-Konstituenten) -> index_constituents.

Idempotent — ON CONFLICT DO NOTHING. Behebt Survivorship-Bias (FIX-18 / Kap. 19):
Snapshots nur für Titel bilden, die zum Snap-Datum im Index waren.

Enthält delistete Titel (CSGN, BALN) mit valid_to-Datum, damit historische
Signale korrekt ausgewertet werden können.

Aufruf:  uv run python scripts/seed_index_constituents.py
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.config import get_settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed_index_constituents")

# ---------------------------------------------------------------------------
# SMI-20 — aktuell (Stand Juni 2026)
# valid_from = 2015-01-01 (Start unseres Datenbereichs).
# valid_to = None -> aktuell im Index.
# ---------------------------------------------------------------------------
_d = date.fromisoformat

SMI_CURRENT: list[tuple[str, date, date | None]] = [
    # (ticker, valid_from, valid_to)
    ("NESN", _d("2015-01-01"), None),
    ("NOVN", _d("2015-01-01"), None),
    ("ROG", _d("2015-01-01"), None),
    ("UBSG", _d("2015-01-01"), None),
    ("ZURN", _d("2015-01-01"), None),
    ("ABBN", _d("2015-01-01"), None),
    ("LONN", _d("2015-01-01"), None),
    ("SIKA", _d("2015-01-01"), None),
    ("GIVN", _d("2015-01-01"), None),
    ("CFR", _d("2015-01-01"), None),
    ("ALC", _d("2019-10-01"), None),  # Alcon: Abspaltung von Novartis, SMI-Aufnahme Q4-2019
    ("HOLN", _d("2015-01-01"), None),
    ("SLHN", _d("2015-01-01"), None),
    ("GEBN", _d("2015-01-01"), None),
    ("SCMN", _d("2015-01-01"), None),
    ("SOON", _d("2015-01-01"), None),
    ("LOGN", _d("2015-01-01"), None),
    ("PGHN", _d("2015-01-01"), None),
    ("SREN", _d("2015-01-01"), None),
    ("BAER", _d("2015-01-01"), None),
]

# ---------------------------------------------------------------------------
# SMI-Historisch — delistet oder inzwischen aus dem Index entfernt.
# valid_to = letzter Handelstag bzw. bekanntes Delisting-/Austausch-Datum.
# ---------------------------------------------------------------------------
SMI_HISTORICAL: list[tuple[str, date, date | None]] = [
    # Credit Suisse: SMI-Mitglied bis Übernahme durch UBS (Vollzug 2023-06-12)
    ("CSGN", _d("2015-01-01"), _d("2023-06-12")),
    # Baloise: SMI-Mitglied; Fusion mit Helvetia 2025 (Delisting ca. Mai 2025)
    ("BALN", _d("2015-01-01"), _d("2025-05-30")),
]

# ---------------------------------------------------------------------------
# SMIM-30 — Auswahl historisch relevanter Titel (nicht vollständig, erweiterbar).
# Diese Titel werden für Krypto-Vergleich und Risikostreaming genutzt.
# ---------------------------------------------------------------------------
SMIM_CURRENT: list[tuple[str, date, date | None]] = [
    ("KNIN", _d("2015-01-01"), None),
    ("STMN", _d("2015-01-01"), None),
    ("UHR", _d("2015-01-01"), None),
    ("SGKN", _d("2015-01-01"), None),
    ("AMSN", _d("2015-01-01"), None),
    ("BARN", _d("2015-01-01"), None),
    ("VACN", _d("2015-01-01"), None),
    ("TEMN", _d("2015-01-01"), None),
    ("WKBN", _d("2015-01-01"), None),
    ("DKSH", _d("2015-01-01"), None),
]


async def seed_constituents(
    entries: list[tuple[str, date, date | None]],
    index_name: str,
) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    count = 0
    async with session_factory() as session:
        for ticker, valid_from, valid_to in entries:
            result = await session.execute(
                text("""
                    INSERT INTO index_constituents
                        (id, index_name, ticker, valid_from, valid_to)
                    VALUES
                        (:id, :index_name, :ticker, :valid_from, :valid_to)
                    ON CONFLICT (index_name, ticker, valid_from) DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "index_name": index_name,
                    "ticker": ticker,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                },
            )
            count += result.rowcount
        await session.commit()
    await engine.dispose()
    return count


async def main() -> None:
    log.info("Seeding SMI current members …")
    n = await seed_constituents(SMI_CURRENT, "SMI")
    log.info("  SMI current: %d rows inserted", n)

    log.info("Seeding SMI historical/delisted members …")
    n = await seed_constituents(SMI_HISTORICAL, "SMI")
    log.info("  SMI historical: %d rows inserted", n)

    log.info("Seeding SMIM current members …")
    n = await seed_constituents(SMIM_CURRENT, "SMIM")
    log.info("  SMIM current: %d rows inserted", n)

    log.info("FERTIG seed_index_constituents — alle Einträge idempotent.")


if __name__ == "__main__":
    asyncio.run(main())
