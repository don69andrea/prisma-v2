"""Bootstrap-Seed: PIT-Fundamentals -> stock_fundamentals.

Provider wird über --provider gewählt (default: config.dataset_source_fundamentals).
'auto' = den von verify_dataset_coverage.py empfohlenen Provider nutzen.
Schreibt NUR, wenn echte Daten kommen — KEIN Stub-Fallback (CHALLENGE 01).

Aufruf:  uv run python scripts/seed_fundamentals.py --provider auto --from 2015-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date

from backend.application.pipeline.load import bulk_upsert
from backend.config import get_settings
from backend.infrastructure.adapters.eodhd_fundamentals_adapter import (
    EodhdFundamentalsAdapter,
)
from scripts.seed_historical_prices import SMI

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed_fundamentals")


def _build_provider(name: str):
    s = get_settings()
    if name in ("auto", "eodhd"):
        return "eodhd", EodhdFundamentalsAdapter(s.eodhd_api_key)
    # TODO: 'fmp' (fmp_adapter), 'simfin_us' (simfin_adapter market='us'), 'yf_derived'
    raise NotImplementedError(f"Provider '{name}' noch nicht verdrahtet — siehe README §0")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="auto")
    ap.add_argument("--from", dest="start", default="2015-01-01")
    ap.add_argument("--tickers", nargs="*", default=SMI)
    args = ap.parse_args()
    start = date.fromisoformat(args.start)

    name, adapter = _build_provider(args.provider)
    if not getattr(adapter, "enabled", True):
        log.error("Provider %s ist deaktiviert (kein API-Key). ABBRUCH — kein Stub.", name)
        raise SystemExit(1)

    total = 0
    for t in args.tickers:
        try:
            rows = await adapter.fetch_quarterly(t)
            rows = [r for r in rows if r["period_end"] >= start]
            if not rows:
                log.warning("%s: keine Fundamentals (Coverage-Lücke!)", t)
                continue
            total += await bulk_upsert("stock_fundamentals", rows)
        except Exception as e:  # noqa: BLE001
            log.error("%s fehlgeschlagen: %s", t, e)
    log.info("FERTIG seed_fundamentals (%s): %d Zeilen", name, total)


if __name__ == "__main__":
    asyncio.run(main())
