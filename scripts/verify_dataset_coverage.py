"""PHASE-0-GATE — entscheidet die Fundamentals-Quelle anhand echter Coverage.

Testet FMP, EODHD und SimFin-US an je 3 Probe-Titeln und schreibt
docs/dataset_coverage.md mit einer Empfehlung. KEIN weiterer Bau, bevor das
grün ist (CHALLENGE 01 / FIX-14).

Akzeptanz pro Quelle/Titel: >= 20 Quartale mit < 20% Nulls.

Aufruf:  uv run python scripts/verify_dataset_coverage.py
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.config import get_settings
from backend.infrastructure.adapters.eodhd_fundamentals_adapter import (
    EodhdFundamentalsAdapter,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("verify_coverage")

PROBE_CH = ["NESN", "NOVN", "ROG"]  # SMI-Schwergewichte
PROBE_US = ["AAPL", "MSFT", "JNJ"]  # SimFin-US-Referenz
MIN_QUARTERS = 20
MAX_NULL_RATE = 0.20

_NUM_FIELDS = [
    "pe_ratio",
    "roe",
    "debt_equity",
    "fcf_margin",
    "eps_chf",
    "dividend_yield",
    "market_cap_chf",
]


def _coverage(rows: list[dict]) -> tuple[int, float]:
    if not rows:
        return 0, 1.0
    total = len(rows) * len(_NUM_FIELDS)
    nulls = sum(1 for r in rows for f in _NUM_FIELDS if r.get(f) in (None, 0, 0.0))
    return len(rows), nulls / total if total else 1.0


async def _probe_eodhd(tickers: list[str]) -> dict[str, tuple[int, float]]:
    s = get_settings()
    ad = EodhdFundamentalsAdapter(s.eodhd_api_key)
    out = {}
    for t in tickers:
        rows = await ad.fetch_quarterly(t)
        out[t] = _coverage(rows)
    return out


# Platzhalter — analog implementieren, sobald FMP/SimFin-Adapter Quartals-Dicts liefern.
async def _probe_fmp(tickers):
    return {t: (0, 1.0) for t in tickers}  # TODO: fmp_adapter


async def _probe_simfin_us(tickers):
    return {t: (0, 1.0) for t in tickers}  # TODO: simfin_adapter (market='us')


def _verdict(cov: dict[str, tuple[int, float]]) -> bool:
    return all(q >= MIN_QUARTERS and nr <= MAX_NULL_RATE for q, nr in cov.values())


async def main() -> None:
    results = {
        "eodhd (CH)": await _probe_eodhd(PROBE_CH),
        "fmp (CH)": await _probe_fmp(PROBE_CH),
        "simfin_us (US-Proxy)": await _probe_simfin_us(PROBE_US),
    }

    lines = [
        "# Dataset Coverage Report",
        "",
        f"Akzeptanz: >= {MIN_QUARTERS} Quartale, < {int(MAX_NULL_RATE * 100)}% Nulls.",
        "",
        "| Quelle | Titel | Quartale | Null-Quote | ok |",
        "|---|---|---|---|---|",
    ]
    recommended = None
    for src, cov in results.items():
        for t, (q, nr) in cov.items():
            ok = "✅" if (q >= MIN_QUARTERS and nr <= MAX_NULL_RATE) else "❌"
            lines.append(f"| {src} | {t} | {q} | {nr:.0%} | {ok} |")
        if recommended is None and _verdict(cov):
            recommended = src

    lines += [
        "",
        f"## Empfehlung: **{recommended or 'KEINE Quelle besteht — Plan B (US-Proxy) wählen'}**",
        "",
    ]
    if recommended:
        lines.append("→ in backend/config.py `dataset_source_fundamentals` entsprechend setzen.")
    else:
        lines.append("→ SimFin-US-Proxy-Setup als ML-Methodik-Datensatz nutzen, Swiss nur Live.")

    out = Path("docs/dataset_coverage.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report -> %s | Empfehlung: %s", out, recommended)
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
