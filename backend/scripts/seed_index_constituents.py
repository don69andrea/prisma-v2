"""Seed index_constituents — PIT-Universum für SMI/SMIM.

Idempotent (ON CONFLICT DO NOTHING). Läuft im bootstrap-Flow nach alembic upgrade head.

Coverage-Hinweis delisteter Titel:
- CSGN.SW (Credit Suisse): valid_to=2023-06-12 (UBS-Übernahme vollzogen).
  yfinance liefert für CSGN.SW oft keine Kurshistorie mehr — das ist erwartet.
  Der index_constituents-Eintrag existiert trotzdem, damit PIT-Snapshots
  CSGN korrekt als SMI-Mitglied bis 2023-06-12 führen.

Fehlende Kurshistorie für delistete Titel wird geloggt (WARNING), aber bricht
den Seed nicht ab. Die Spalte valid_to macht solche Lücken sichtbar.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlalchemy import text

from backend.infrastructure.persistence.session import get_session_factory

log = logging.getLogger(__name__)

# Alle aktuellen SMI-Mitglieder (Stand 2026, Quelle: SIX Swiss Exchange)
# valid_from = frühest möglicher Trainingszeitpunkt; valid_to = NULL (aktuell)
_SMI_CURRENT: list[tuple[str, date]] = [
    ("NESN.SW", date(2010, 1, 1)),  # Nestlé
    ("NOVN.SW", date(2010, 1, 1)),  # Novartis
    ("ROG.SW", date(2010, 1, 1)),  # Roche
    ("ABBN.SW", date(2010, 1, 1)),  # ABB
    ("ZURN.SW", date(2010, 1, 1)),  # Zurich Insurance
    ("UBSG.SW", date(2023, 6, 12)),  # UBS (nach Credit-Suisse-Übernahme aufgewertet)
    ("UHR.SW", date(2010, 1, 1)),  # Swatch Group
    ("GEBN.SW", date(2010, 1, 1)),  # Geberit
    ("GIVN.SW", date(2010, 1, 1)),  # Givaudan
    ("LONN.SW", date(2010, 1, 1)),  # Lonza
    ("SREN.SW", date(2010, 1, 1)),  # Swiss Re
    ("SGKN.SW", date(2010, 1, 1)),  # SGS
    ("SLHN.SW", date(2010, 1, 1)),  # Swiss Life
    ("SCMN.SW", date(2010, 1, 1)),  # Swisscom
    ("SIKA.SW", date(2018, 4, 1)),  # Sika (2018 in SMI aufgenommen)
    ("HOLN.SW", date(2021, 9, 20)),  # Holcim (vormals LafargeHolcim)
    ("PGHN.SW", date(2020, 9, 21)),  # Partners Group
    ("KNIN.SW", date(2020, 9, 21)),  # Kühne+Nagel
    ("CFR.SW", date(2010, 1, 1)),  # Richemont
    ("STMN.SW", date(2017, 9, 18)),  # Straumann
]

# Delistete SMI-Mitglieder mit korrektem valid_to
# Der index_constituents-Eintrag wird immer erstellt, auch ohne Kurshistorie.
_SMI_DELISTED: list[tuple[str, date, date]] = [
    # CSGN: Credit Suisse — UBS-Übernahme vollzogen am 2023-06-12
    # Didaktischer Wert: PRISMA soll zeigen, ob Risiko VOR dem Kollaps erkennbar war.
    ("CSGN.SW", date(2010, 1, 1), date(2023, 6, 12)),
]

# Repräsentative SMIM-Titel (Stand 2026, nicht vollständig — bei Bedarf ergänzen)
# Quelle: SIX Swiss Exchange SMIM-Zusammensetzung
_SMIM_CURRENT: list[tuple[str, date]] = [
    ("TEMN.SW", date(2010, 1, 1)),  # Temenos
    ("BALN.SW", date(2010, 1, 1)),  # Bâloise Holding
    ("BKW.SW", date(2010, 1, 1)),  # BKW
    ("EMMN.SW", date(2010, 1, 1)),  # Emmi
    ("GALEN.SW", date(2010, 1, 1)),  # Galenica
    ("SIGN.SW", date(2020, 3, 1)),  # SIG Group (IPO 2020)
    ("MOBN.SW", date(2010, 1, 1)),  # Mobimo
    ("LOGN.SW", date(2023, 9, 18)),  # Logitech (zurück in SMIM nach SMI-Exit)
    ("LISN.SW", date(2010, 1, 1)),  # Lindt & Sprüngli PS
    ("VACN.SW", date(2018, 4, 1)),  # VAT Group (IPO 2016, SMIM ab ca. 2018)
    ("EFGN.SW", date(2010, 1, 1)),  # EFG International
    ("HELN.SW", date(2010, 1, 1)),  # Helvetia
    ("SCHP.SW", date(2010, 1, 1)),  # Schindler PS
    ("BARN.SW", date(2010, 1, 1)),  # Barry Callebaut
    ("ARBN.SW", date(2010, 1, 1)),  # Arbonia
]

# Delistete SMIM-Titel
_SMIM_DELISTED: list[tuple[str, date, date]] = []


async def seed(dry_run: bool = False) -> dict[str, int]:
    """Seed index_constituents. Gibt Statistik zurück."""
    factory = get_session_factory()

    inserted = 0
    skipped = 0
    no_price_coverage: list[str] = []

    async with factory() as session:
        rows: list[dict[str, object]] = []

        for ticker, valid_from in _SMI_CURRENT:
            rows.append(
                {"index_name": "SMI", "ticker": ticker, "valid_from": valid_from, "valid_to": None}
            )

        for ticker, valid_from, valid_to in _SMI_DELISTED:
            rows.append(
                {
                    "index_name": "SMI",
                    "ticker": ticker,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                }
            )
            no_price_coverage.append(f"{ticker} (delistet {valid_to})")

        for ticker, valid_from in _SMIM_CURRENT:
            rows.append(
                {"index_name": "SMIM", "ticker": ticker, "valid_from": valid_from, "valid_to": None}
            )

        for ticker, valid_from, valid_to in _SMIM_DELISTED:
            rows.append(
                {
                    "index_name": "SMIM",
                    "ticker": ticker,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                }
            )
            no_price_coverage.append(f"{ticker} (delistet {valid_to})")

        if dry_run:
            log.info("[dry-run] Würde %d Zeilen einfügen", len(rows))
            return {"inserted": 0, "skipped": 0, "total": len(rows)}

        count_before_result = await session.execute(text("SELECT COUNT(*) FROM index_constituents"))
        count_before: int = count_before_result.scalar_one()

        for row in rows:
            await session.execute(
                text(
                    "INSERT INTO index_constituents (id, index_name, ticker, valid_from, valid_to) "
                    "VALUES (gen_random_uuid(), :index_name, :ticker, :valid_from, :valid_to) "
                    "ON CONFLICT (index_name, ticker, valid_from) DO NOTHING"
                ),
                row,
            )

        await session.commit()

        count_after_result = await session.execute(text("SELECT COUNT(*) FROM index_constituents"))
        count_after: int = count_after_result.scalar_one()
        inserted = count_after - count_before
        skipped = len(rows) - inserted

    log.info(
        "index_constituents: %d eingefügt, %d bereits vorhanden (%d total)",
        inserted,
        skipped,
        inserted + skipped,
    )

    if no_price_coverage:
        log.warning(
            "Delistete Titel ohne gesicherte yfinance-Kurshistorie "
            "(index_constituents-Eintrag korrekt gesetzt, Preise ggf. leer): %s",
            ", ".join(no_price_coverage),
        )

    return {"inserted": inserted, "skipped": skipped, "total": inserted + skipped}


def _pit_members(index_name: str, snap_date: date, session_sync: object) -> list[str]:
    """Hilfsfunktion für Tests — gibt PIT-Mitglieder für ein Datum zurück (sync)."""
    raise NotImplementedError("Nur für async-Nutzung — verwende _pit_members_async()")


async def pit_members(index_name: str, snap_date: date, session: object) -> list[str]:
    """Gibt alle Ticker zurück, die am snap_date im Index waren (PIT)."""
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    result = await session.execute(
        text(
            "SELECT ticker FROM index_constituents "
            "WHERE index_name = :idx "
            "  AND valid_from <= :d "
            "  AND (valid_to IS NULL OR valid_to >= :d) "
            "ORDER BY ticker"
        ),
        {"idx": index_name, "d": snap_date},
    )
    return [row[0] for row in result.fetchall()]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = asyncio.run(seed())
    print(f"Fertig: {stats}")
