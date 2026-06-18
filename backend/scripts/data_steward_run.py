"""Data Steward Cron — täglich 06:00 UTC via Render."""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("data_steward_run")


async def main() -> None:
    from backend.application.agents.data_steward_agent import (
        DataStewardAgent,  # noqa: PLC0415, F401
    )

    log.info("DataSteward gestartet")
    # In production: inject real dependencies via DI container
    # For now: lightweight stub that can be extended
    log.info("DataSteward: Keine Datenbankverbindung konfiguriert — nur Logging-Modus")


if __name__ == "__main__":
    asyncio.run(main())
