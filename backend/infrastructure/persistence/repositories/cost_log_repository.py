"""SQLAlchemy-Implementierung des CostLogRepository-Ports.

Wichtig: jede Methode öffnet eine **eigene Session** — Audit-Inserts
dürfen nicht an Request-Sessions gekoppelt sein, sonst würde ein
`record()` mitten in einem Stock-Service-Request laufende
Business-Operationen mit-committen.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §5 + §9.
"""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.cost_summary import (
    CallEntry,
    CostBreakdown,
    FeatureBreakdown,
    ModelBreakdown,
)
from backend.domain.repositories.cost_log_repository import (
    CostLogEntry,
    CostLogRepository,
)
from backend.infrastructure.persistence.models.llm_call_log import LLMCallLogORM

# ---------------------------------------------------------------------------
# SQL-Queries (module-level Konstanten)
# ---------------------------------------------------------------------------

# Kalender-Monat UTC, synchron mit Anthropic-Console Spend-Limit.
# Kein ORM-Layer für diese Performance-kritischen Read-Queries.
_CURRENT_MONTH_SUM_SQL = text(
    """
    SELECT COALESCE(SUM(cost_usd), 0)
    FROM llm_call_log
    WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
      AND created_at <  date_trunc('month', now() AT TIME ZONE 'UTC')
                         + INTERVAL '1 month'
    """
)

_BY_MODEL_SQL = text(
    """
    SELECT model, COUNT(*) AS calls, SUM(cost_usd) AS cost_usd
    FROM llm_call_log
    WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
      AND created_at <  date_trunc('month', now() AT TIME ZONE 'UTC')
                         + INTERVAL '1 month'
    GROUP BY model
    ORDER BY cost_usd DESC
    """
)

_BY_FEATURE_SQL = text(
    """
    SELECT feature, COUNT(*) AS calls, SUM(cost_usd) AS cost_usd
    FROM llm_call_log
    WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
      AND created_at <  date_trunc('month', now() AT TIME ZONE 'UTC')
                         + INTERVAL '1 month'
    GROUP BY feature
    ORDER BY cost_usd DESC
    """
)

_LAST_CALLS_SQL = text(
    """
    SELECT created_at, model, feature, cost_usd
    FROM llm_call_log
    WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
      AND created_at <  date_trunc('month', now() AT TIME ZONE 'UTC')
                         + INTERVAL '1 month'
    ORDER BY created_at DESC
    LIMIT :limit
    """
)

# Advisory Lock Key: stabiler Hash für PRISMA Budget-Cap.
# pg_try_advisory_xact_lock hält den Lock bis zum Transaktions-Ende —
# verhindert Race Conditions zwischen mehreren Backend-Instanzen.
_BUDGET_CAP_LOCK_KEY = 7_273_948_201  # hash("prisma_budget_cap") % 2^31

_CAP_CHECK_ATOMIC_SQL = text(
    """
    SELECT
        pg_try_advisory_xact_lock(:lock_key)
        AND (
            COALESCE((
                SELECT SUM(cost_usd)
                FROM llm_call_log
                WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
                  AND created_at <  date_trunc('month', now() AT TIME ZONE 'UTC')
                                     + INTERVAL '1 month'
            ), 0) + :estimated_usd
        ) <= :cap_usd * :threshold
    """
)


class SQLACostLogRepository(CostLogRepository):
    """Persistiert Audit-Einträge und liefert Aggregate via async SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, entry: CostLogEntry) -> None:
        orm = LLMCallLogORM(
            provider=entry.provider,
            model=entry.model,
            feature=entry.feature,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            cost_usd=entry.cost_usd,
            request_id=entry.request_id,
        )
        async with self._session_factory() as session:
            session.add(orm)
            await session.commit()

    async def current_month_total_usd(self) -> Decimal:
        async with self._session_factory() as session:
            result = await session.execute(_CURRENT_MONTH_SUM_SQL)
            # COALESCE garantiert nicht-NULL; Driver liefert Decimal oder int
            raw = result.scalar_one()
            return Decimal(str(raw))

    async def check_cap_atomic(self, estimated_usd: Decimal, cap_usd: Decimal, threshold: Decimal) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    _CAP_CHECK_ATOMIC_SQL,
                    {
                        "lock_key": _BUDGET_CAP_LOCK_KEY,
                        "estimated_usd": str(estimated_usd),
                        "cap_usd": str(cap_usd),
                        "threshold": str(threshold),
                    },
                )
                return bool(result.scalar_one())

    async def current_month_breakdown(self, last_n: int) -> CostBreakdown:
        async with self._session_factory() as session:
            model_result = await session.execute(_BY_MODEL_SQL)
            by_model = sorted(
                [
                    ModelBreakdown(
                        model=row.model,
                        calls=row.calls,
                        cost_usd=Decimal(str(row.cost_usd)),
                    )
                    for row in model_result.fetchall()
                ],
                key=lambda b: b.cost_usd,
                reverse=True,
            )

            feature_result = await session.execute(_BY_FEATURE_SQL)
            by_feature = sorted(
                [
                    FeatureBreakdown(
                        feature=row.feature,
                        calls=row.calls,
                        cost_usd=Decimal(str(row.cost_usd)),
                    )
                    for row in feature_result.fetchall()
                ],
                key=lambda b: b.cost_usd,
                reverse=True,
            )

            last_result = await session.execute(_LAST_CALLS_SQL, {"limit": last_n})
            last_calls = [
                CallEntry(
                    created_at=row.created_at,
                    model=row.model,
                    feature=row.feature,
                    cost_usd=Decimal(str(row.cost_usd)),
                )
                for row in last_result.fetchall()
            ]

        return CostBreakdown(
            by_model=by_model,
            by_feature=by_feature,
            last_calls=last_calls,
        )
