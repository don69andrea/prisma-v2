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
from datetime import date
from pathlib import Path

from backend.config import get_settings
from backend.infrastructure.adapters.eodhd_fundamentals_adapter import (
    EodhdFundamentalsAdapter,
)
from backend.infrastructure.adapters.fmp_fundamentals_adapter import (
    FmpFundamentalsAdapter,
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
    """EODHD-Probe: übersprungen wenn kein EODHD_API_KEY gesetzt ist."""
    s = get_settings()
    ad = EodhdFundamentalsAdapter(s.eodhd_api_key)
    if not ad.enabled:
        log.info("EODHD: kein Key gesetzt — übersprungen (0 Quartale)")
        return {t: (0, 1.0) for t in tickers}
    out = {}
    for t in tickers:
        rows = await ad.fetch_quarterly(t)
        out[t] = _coverage(rows)
    return out


async def _probe_fmp(tickers: list[str]) -> dict[str, tuple[int, float]]:
    """FMP-Probe: über den vorhandenen fmp_api_key aus config.py."""
    s = get_settings()
    ad = FmpFundamentalsAdapter(s.fmp_api_key)
    if not ad.enabled:
        log.info("FMP: kein Key gesetzt (oder Platzhalter) — übersprungen (0 Quartale)")
        return {t: (0, 1.0) for t in tickers}
    out = {}
    for t in tickers:
        rows = await ad.fetch_quarterly(t)
        out[t] = _coverage(rows)
    return out


async def _probe_simfin_us(tickers: list[str]) -> dict[str, tuple[int, float]]:
    """SimFin-US-Probe: zählt verfügbare Quartale aus dem bulk-Download.

    Gibt (0, 1.0) zurück wenn:
    - simfin-Package nicht installiert (`pip install simfin`)
    - kein SIMFIN_API_KEY in config
    - SimFin-Download schlägt fehl
    """
    s = get_settings()
    if not s.simfin_api_key:
        log.info("SimFin: kein Key gesetzt — übersprungen (0 Quartale)")
        return {t: (0, 1.0) for t in tickers}

    try:
        from backend.infrastructure.adapters.simfin_adapter import SimFinAdapter
    except ImportError:
        log.info("SimFin: Package 'simfin' nicht installiert — übersprungen")
        return {t: (0, 1.0) for t in tickers}

    try:
        adapter = SimFinAdapter(api_key=s.simfin_api_key)
        # _ensure_us_loaded() lädt income/balance/prices bulk für 'us'
        await asyncio.to_thread(adapter._ensure_us_loaded)  # noqa: SLF001
    except Exception as exc:
        log.warning("SimFin US bulk-Download fehlgeschlagen: %s", exc)
        return {t: (0, 1.0) for t in tickers}

    out = {}
    today = date.today()
    for t in tickers:
        income_df = adapter._income_us.get(t)  # noqa: SLF001
        if income_df is None or income_df.empty:
            out[t] = (0, 1.0)
            continue
        # Zähle verfügbare Quartale (Publish Date bis heute)
        published = income_df[income_df["Publish Date"] <= str(today)]
        n_quarters = len(published)

        # Coverage: P/E und EPS prüfen über get_fundamentals_on_date() an einem Testdatum
        snap = date(2022, 6, 30)
        f = adapter.get_fundamentals_on_date(t, snap, market="us")
        null_count = sum(
            1
            for field in _NUM_FIELDS
            if f is None or getattr(f, field.replace("_chf", ""), None) in (None,)
        )
        null_rate = null_count / len(_NUM_FIELDS)
        out[t] = (n_quarters, null_rate)
    return out


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
        f"Generiert: {date.today().isoformat()} | "
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
        lines.append(
            f'→ in backend/config.py `dataset_source_fundamentals` setzen: `"{recommended.split()[0]}"`'
        )
    else:
        lines.append(
            '→ `dataset_source_fundamentals = "simfin_us"` als ML-Methodik-Datensatz verwenden.\n'
            "→ Swiss-Live-Signale nutzen yfinance `.info` für approximierte Fundamentals."
        )

    lines += [
        "",
        "## Entscheidungsregel",
        "",
        '1. Wenn FMP >= 20 Quartale mit < 20% Nulls für alle Probe-Titel: `dataset_source_fundamentals = "fmp"`',
        '2. Sonst wenn EODHD Key vorhanden und besteht: `dataset_source_fundamentals = "eodhd"`',
        '3. Sonst: `dataset_source_fundamentals = "simfin_us"` (US-Proxy, akademisch reproduzierbar).',
        "",
        "Referenz: PRISMA V3 Spec CHALLENGE 01 / Kap. 15.5.",
    ]

    out = Path("docs/dataset_coverage.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report -> %s | Empfehlung: %s", out, recommended)
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
