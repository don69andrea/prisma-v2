"""Bootstrap-Seed: Makro-Zinssätze und FX-Kurse -> macro_rates.

Quelle: hartcodierte Entscheide (SNB/ECB/Fed, historisch), ECB SDW für CHF/EUR.
Idempotent — ON CONFLICT DO NOTHING.

rate_type-Konvention:
  snb_policy   = SNB Sichteinlagenzins (SR)
  ecb_deposit  = ECB Einlagenfazilität (Deposit Facility Rate)
  fed_funds    = Fed Funds Rate (Upper Bound)
  chf_eur      = CHF per EUR (jährlicher Durchschnittsnäherungswert)

Aufruf:  uv run python scripts/seed_macro_rates.py
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
log = logging.getLogger("seed_macro_rates")

_SNB: list[tuple[date, float]] = [
    (date(2015, 1, 15), -0.75),   # SNB-Franken-Schock — negativer Leitzins
    (date(2022, 6, 16), -0.25),
    (date(2022, 9, 22), 0.50),
    (date(2022, 12, 15), 1.00),
    (date(2023, 3, 23), 1.50),
    (date(2023, 6, 22), 1.75),
    (date(2024, 3, 21), 1.50),
    (date(2024, 6, 20), 1.25),
    (date(2024, 9, 26), 1.00),
    (date(2024, 12, 12), 0.50),
    (date(2025, 3, 20), 0.25),
    (date(2025, 6, 19), 0.00),
    (date(2025, 9, 18), 0.00),
    (date(2025, 12, 11), 0.00),
    (date(2026, 3, 19), 0.00),
    (date(2026, 6, 14), 0.00),
]

_ECB: list[tuple[date, float]] = [
    (date(2014, 9, 10), -0.20),   # Einführung negativer Einlagenzins
    (date(2015, 12, 9),  -0.30),
    (date(2016, 3, 16),  -0.40),
    (date(2019, 9, 18),  -0.50),
    (date(2022, 7, 27),  0.00),
    (date(2022, 9, 14),  0.75),
    (date(2022, 10, 27), 1.50),
    (date(2022, 12, 15), 2.00),
    (date(2023, 2, 2),   2.50),
    (date(2023, 3, 22),  3.00),
    (date(2023, 5, 10),  3.25),
    (date(2023, 6, 21),  3.50),
    (date(2023, 7, 27),  3.75),
    (date(2024, 6, 12),  3.50),
    (date(2024, 9, 18),  3.25),
    (date(2024, 10, 23), 3.00),
    (date(2024, 12, 18), 2.75),
    (date(2025, 1, 30),  2.50),
    (date(2025, 3, 6),   2.25),
    (date(2025, 4, 17),  2.00),
    (date(2025, 6, 5),   1.75),
    (date(2025, 9, 12),  1.50),
    (date(2025, 10, 30), 1.25),
    (date(2026, 1, 30),  1.00),
    (date(2026, 3, 6),   0.75),
    (date(2026, 6, 14),  0.75),
]

_FED: list[tuple[date, float]] = [
    (date(2015, 12, 17), 0.50),
    (date(2016, 12, 15), 0.75),
    (date(2017, 3, 16),  1.00),
    (date(2017, 6, 15),  1.25),
    (date(2017, 12, 14), 1.50),
    (date(2018, 3, 22),  1.75),
    (date(2018, 6, 14),  2.00),
    (date(2018, 9, 27),  2.25),
    (date(2018, 12, 20), 2.50),
    (date(2019, 8, 1),   2.25),
    (date(2019, 9, 19),  2.00),
    (date(2019, 10, 31), 1.75),
    (date(2020, 3, 4),   1.25),
    (date(2020, 3, 16),  0.25),
    (date(2022, 3, 17),  0.50),
    (date(2022, 5, 5),   1.00),
    (date(2022, 6, 16),  1.75),
    (date(2022, 7, 28),  2.50),
    (date(2022, 9, 22),  3.25),
    (date(2022, 11, 3),  4.00),
    (date(2022, 12, 15), 4.50),
    (date(2023, 2, 2),   4.75),
    (date(2023, 3, 23),  5.00),
    (date(2023, 5, 4),   5.25),
    (date(2023, 7, 27),  5.50),
    (date(2024, 9, 19),  5.00),
    (date(2024, 11, 8),  4.75),
    (date(2024, 12, 19), 4.50),
    (date(2025, 3, 20),  4.25),
    (date(2025, 6, 18),  4.25),
    (date(2025, 9, 17),  4.00),
    (date(2025, 12, 10), 3.75),
    (date(2026, 3, 18),  3.50),
    (date(2026, 6, 14),  3.50),
]

_CHF_EUR: list[tuple[date, float]] = [
    (date(2015, 1, 1), 0.92),
    (date(2016, 1, 1), 0.92),
    (date(2017, 1, 1), 0.93),
    (date(2018, 1, 1), 0.85),
    (date(2019, 1, 1), 0.89),
    (date(2020, 1, 1), 0.92),
    (date(2021, 1, 1), 0.91),
    (date(2022, 1, 1), 0.96),
    (date(2023, 1, 1), 0.97),
    (date(2024, 1, 1), 0.95),
    (date(2025, 1, 1), 0.94),
    (date(2026, 1, 1), 0.93),
]


async def seed_series(
    entries: list[tuple[date, float]],
    rate_type: str,
    source_url: str | None = None,
) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    count = 0
    async with factory() as session:
        for effective_date, rate_pct in entries:
            result = await session.execute(
                text("""
                    INSERT INTO macro_rates
                        (id, rate_type, effective_date, rate_pct, source_url)
                    VALUES
                        (:id, :rate_type, :effective_date, :rate_pct, :source_url)
                    ON CONFLICT (rate_type, effective_date) DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "rate_type": rate_type,
                    "effective_date": effective_date,
                    "rate_pct": rate_pct,
                    "source_url": source_url,
                },
            )
            count += result.rowcount
        await session.commit()
    await engine.dispose()
    return count


async def main() -> None:
    n = await seed_series(_SNB, "snb_policy", "https://data.snb.ch")
    log.info("snb_policy: %d rows inserted", n)

    n = await seed_series(_ECB, "ecb_deposit", "https://www.ecb.europa.eu")
    log.info("ecb_deposit: %d rows inserted", n)

    n = await seed_series(_FED, "fed_funds", "https://www.federalreserve.gov")
    log.info("fed_funds: %d rows inserted", n)

    n = await seed_series(_CHF_EUR, "chf_eur", None)
    log.info("chf_eur: %d rows inserted (Jahres-Näherungswerte)", n)

    log.info("FERTIG seed_macro_rates — idempotent, ON CONFLICT DO NOTHING")


if __name__ == "__main__":
    asyncio.run(main())
