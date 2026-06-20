"""SignalOutcomeRepository — Kap. 5.1 / CHALLENGE 03.

Repository-Pattern: alle DB-Writes über diese Klasse, nie direkt.
Nutzt eigene Session (übergeben via Constructor).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SignalOutcomeRepository:
    """UPSERT- und Query-Interface für signal_outcomes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, row: dict[str, Any]) -> None:
        """Idempotenter UPSERT via UNIQUE(ticker, signal_date, horizon_days)."""
        if "id" not in row or not row["id"]:
            row = {**row, "id": str(uuid.uuid4())}
        stmt = text(
            """
            INSERT INTO signal_outcomes
                (id, ticker, asset_type, signal_date, signal, price_at_signal,
                 horizon_days, evaluation_date, price_at_eval, actual_return,
                 benchmark_ret, excess_return, cost_adjusted_return,
                 net_excess_return, was_correct, used_for_train, source_table)
            VALUES
                (:id, :ticker, :asset_type, :signal_date, :signal, :price_at_signal,
                 :horizon_days, :evaluation_date, :price_at_eval, :actual_return,
                 :benchmark_ret, :excess_return, :cost_adjusted_return,
                 :net_excess_return, :was_correct, :used_for_train, :source_table)
            ON CONFLICT (ticker, signal_date, horizon_days)
            DO UPDATE SET
                evaluation_date = EXCLUDED.evaluation_date,
                price_at_eval = EXCLUDED.price_at_eval,
                actual_return = EXCLUDED.actual_return,
                benchmark_ret = EXCLUDED.benchmark_ret,
                excess_return = EXCLUDED.excess_return,
                cost_adjusted_return = EXCLUDED.cost_adjusted_return,
                net_excess_return = EXCLUDED.net_excess_return,
                was_correct = EXCLUDED.was_correct
            """
        )
        await self._session.execute(stmt, row)

    async def bulk_upsert(self, rows: list[dict[str, Any]]) -> int:
        """Bulk-UPSERT; gibt Anzahl verarbeiteter Rows zurück."""
        for row in rows:
            await self.upsert(row)
        await self._session.flush()
        return len(rows)

    async def get_by_ticker(
        self, ticker: str, *, evaluated_only: bool = True
    ) -> list[dict[str, Any]]:
        """Alle Outcomes für einen Ticker."""
        where = "ticker = :ticker"
        if evaluated_only:
            where += " AND evaluation_date IS NOT NULL"
        rows = await self._session.execute(
            text(f"SELECT * FROM signal_outcomes WHERE {where} ORDER BY signal_date"),
            {"ticker": ticker},
        )
        return [dict(r._mapping) for r in rows]

    async def get_pending(self, as_of: date) -> list[dict[str, Any]]:
        """Signale ohne Evaluation, deren Horizont abgelaufen ist (≤ as_of)."""
        rows = await self._session.execute(
            text(
                """
                SELECT * FROM signal_outcomes
                WHERE evaluation_date IS NULL
                  AND signal_date + CAST(horizon_days AS INTEGER) <= :as_of
                ORDER BY signal_date
                """
            ),
            {"as_of": as_of},
        )
        return [dict(r._mapping) for r in rows]

    async def win_rate(
        self,
        *,
        asset_type: str | None = None,
        since: date | None = None,
    ) -> dict[str, float]:
        """Net-Win-Rate (cost_adjusted_return > 0), Avg-Return, N."""
        where_parts = ["evaluation_date IS NOT NULL", "cost_adjusted_return IS NOT NULL"]
        params: dict[str, Any] = {}
        if asset_type:
            where_parts.append("asset_type = :asset_type")
            params["asset_type"] = asset_type
        if since:
            where_parts.append("signal_date >= :since")
            params["since"] = since
        where = " AND ".join(where_parts)
        row = await self._session.execute(
            text(
                f"""
                SELECT
                    COUNT(*) as n,
                    AVG(CASE WHEN cost_adjusted_return > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
                    AVG(cost_adjusted_return) as avg_net_return,
                    AVG(net_excess_return) as avg_net_alpha
                FROM signal_outcomes
                WHERE {where}
                """
            ),
            params,
        )
        r = row.fetchone()
        if r is None or r.n == 0:
            return {"n": 0, "win_rate": 0.0, "avg_net_return": 0.0, "avg_net_alpha": 0.0}
        return {
            "n": int(r.n),
            "win_rate": float(r.win_rate or 0.0),
            "avg_net_return": float(r.avg_net_return or 0.0),
            "avg_net_alpha": float(r.avg_net_alpha or 0.0),
        }

    async def delete_all(self) -> int:
        """Für Tests/Seed-Resets — löscht alle Outcomes."""
        result = await self._session.execute(
            text("DELETE FROM signal_outcomes RETURNING id")
        )
        return result.rowcount
