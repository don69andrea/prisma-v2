"""Generischer idempotenter Upsert-Loader für Zeitreihen-Seeds.

Folgt dem Repo-Muster (cost_log_repository): raw SQL via text(), eigene
Session via get_session_factory(). Idempotenz über die UNIQUE-Constraints
der Migrationen 0031/0032/0033 → ON CONFLICT DO NOTHING.

Bewusst KEIN ORM: die Seeds schreiben zig-tausend Zeilen, raw SQL +
executemany ist schneller und konsistent mit den Performance-kritischen
Read-Queries im Repo.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text

from backend.infrastructure.persistence.session import get_session_factory

log = logging.getLogger(__name__)

# table -> (spalten ohne id/created_at, conflict-spalten)
_TABLES: dict[str, tuple[list[str], list[str]]] = {
    "stock_price_history": (
        ["ticker", "date", "open", "high", "low", "close", "volume", "currency", "source"],
        ["ticker", "date"],
    ),
    "crypto_price_history": (
        [
            "ticker",
            "timestamp",
            "interval",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "currency",
            "source",
        ],
        ["ticker", "timestamp", "interval"],
    ),
    "stock_fundamentals": (
        [
            "ticker",
            "period_end",
            "publish_date",
            "period_type",
            "pe_ratio",
            "pb_ratio",
            "ev_ebitda",
            "roe",
            "debt_equity",
            "fcf_margin",
            "eps_chf",
            "eps_growth_yoy",
            "revenue_growth",
            "dividend_yield",
            "dividend_growth",
            "market_cap_chf",
            "sector",
            "source",
        ],
        ["ticker", "period_end", "period_type"],
    ),
}


async def bulk_upsert(table: str, rows: Sequence[dict[str, Any]], batch: int = 500) -> int:
    """Schreibt rows idempotent in `table`. Gibt Anzahl verarbeiteter Zeilen zurück.

    Fehlende optionale Spalten werden mit NULL gefüllt. Mehrfaches Ausführen
    erzeugt keine Duplikate (ON CONFLICT DO NOTHING über UNIQUE-Index).
    """
    if table not in _TABLES:
        raise ValueError(f"Unbekannte Tabelle: {table}")
    if not rows:
        return 0

    cols, conflict = _TABLES[table]
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    sql = text(
        f"INSERT INTO {table} (id, {col_list}) "
        f"VALUES (:id, {placeholders}) "
        f"ON CONFLICT ({', '.join(conflict)}) DO NOTHING"
    )

    factory = get_session_factory()
    total = 0
    async with factory() as session:
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            params = [{"id": str(uuid.uuid4()), **{c: r.get(c) for c in cols}} for r in chunk]
            await session.execute(sql, params)
            total += len(chunk)
        await session.commit()
    log.info("bulk_upsert %s: %d Zeilen verarbeitet", table, total)
    return total
