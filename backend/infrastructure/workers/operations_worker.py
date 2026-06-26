"""Operations Worker: registriert V4-6-Jobs via APScheduler.

Jobs:
  - SignalEvaluationJob: täglich 06:00 Europe/Zurich
  - DriftMonitor: täglich 06:30 Europe/Zurich
  - RetrainingJob: monatlich, 1. des Monats 02:00 Europe/Zurich

Hinweis: _StubPriceProvider ist bewusst als Stub belassen. Der User muss ihn
durch den echten CryptoPriceAdapter ersetzen, sobald eine PG-Instanz läuft.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.infrastructure.adapters.notification_adapter import send_email
from backend.infrastructure.persistence.session import get_session_factory

_logger = logging.getLogger(__name__)

_COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]
_ALERT_TO = "andrea.petretta@students.fhnw.ch"


class _EmailAlertSender:
    async def send_drift_alert(self, flags: list[Any]) -> None:
        if not flags:
            return
        lines = [
            f"  - {f.metric_name} ({f.coin or 'portfolio'}): "
            f"live={f.live_value:.4f} erwartet={f.expected_value:.4f} "
            f"({f.pct_deviation * 100:+.1f}%)"
            for f in flags
        ]
        body = "PRISMA Drift-Alert:\n\n" + "\n".join(lines) + "\n\nBitte Modell-Performance prüfen."
        await send_email(
            to=_ALERT_TO,
            subject=f"[PRISMA] Drift-Alert — {len(flags)} Metrik(en) abweichend",
            body=body,
        )
        _logger.info("Drift-Alert gesendet: %d Flags", len(flags))


class _StubPriceProvider:
    """Stub-Preisabruf — in Produktion durch echten CryptoPriceAdapter ersetzen."""

    async def get_close(self, coin_id: int, asof: date) -> float | None:
        return None

    async def get_history(self, coins: list[str], asof: date) -> pd.DataFrame:
        return pd.DataFrame()


class _MetricsProviderFromDB:
    async def get_latest_metrics(self, window_days: int) -> list[Any]:
        from sqlalchemy import func, select

        from backend.application.jobs.drift_monitor import LiveMetric
        from backend.infrastructure.persistence.models.live_performance_metrics import (
            LivePerformanceMetricORM,
        )

        session_factory = get_session_factory()
        async with session_factory() as session:
            subq = (
                select(
                    LivePerformanceMetricORM.coin_id,
                    func.max(LivePerformanceMetricORM.computed_at).label("max_at"),
                )
                .where(LivePerformanceMetricORM.window_days == window_days)
                .group_by(LivePerformanceMetricORM.coin_id)
                .subquery()
            )
            stmt = select(LivePerformanceMetricORM).join(
                subq,
                (LivePerformanceMetricORM.coin_id == subq.c.coin_id)
                & (LivePerformanceMetricORM.computed_at == subq.c.max_at),
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                LiveMetric(
                    coin_id=r.coin_id,
                    coin=None,
                    live_sharpe=r.live_sharpe,
                    live_calmar=r.live_calmar,
                    vol_mae=r.vol_mae,
                    window_days=r.window_days,
                    n_signals=r.n_signals,
                )
                for r in rows
            ]


async def _run_signal_evaluation() -> None:
    from backend.application.jobs.signal_evaluation_job import SignalEvaluationJob
    from backend.infrastructure.persistence.repositories.live_metrics_repository import (
        SQLALiveMetricsRepository,
    )
    from backend.infrastructure.persistence.repositories.signal_outcomes_repository import (
        SQLASignalOutcomeRepository,
    )

    asof = date.today() - timedelta(days=1)
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        job = SignalEvaluationJob(
            outcome_repo=SQLASignalOutcomeRepository(session),
            metrics_repo=SQLALiveMetricsRepository(session),
            price_provider=_StubPriceProvider(),
        )
        result = await job.run(asof)
        _logger.info("SignalEvaluationJob abgeschlossen: %s", result)


async def _run_drift_monitor() -> None:
    from backend.application.jobs.drift_monitor import DriftMonitor
    from backend.infrastructure.persistence.repositories.drift_flags_repository import (
        SQLADriftFlagRepository,
    )

    asof = date.today()
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        monitor = DriftMonitor(
            flag_repo=SQLADriftFlagRepository(session),
            metrics_provider=_MetricsProviderFromDB(),
            alert_sender=_EmailAlertSender(),
        )
        result = await monitor.run(asof)
        _logger.info("DriftMonitor abgeschlossen: %s", result)


async def _run_retraining() -> None:
    from backend.application.jobs.retraining_job import RetrainingJob
    from backend.infrastructure.persistence.repositories.model_registry_repository import (
        SQLAModelRegistryRepository,
    )

    asof = date.today()
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        job = RetrainingJob(
            model_registry=SQLAModelRegistryRepository(session),
            price_provider=_StubPriceProvider(),
            coins=_COINS,
        )
        result = await job.run(asof)
        _logger.info("RetrainingJob abgeschlossen: %s", result)


def create_operations_scheduler() -> AsyncIOScheduler:
    """Erstellt APScheduler mit V4-6 Operations-Jobs."""
    scheduler = AsyncIOScheduler(timezone="Europe/Zurich")

    scheduler.add_job(
        _run_signal_evaluation,
        trigger=CronTrigger(hour=6, minute=0),
        id="signal_evaluation_daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_drift_monitor,
        trigger=CronTrigger(hour=6, minute=30),
        id="drift_monitor_daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_retraining,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="retraining_monthly",
        replace_existing=True,
    )

    return scheduler
