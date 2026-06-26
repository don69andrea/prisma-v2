"""Operations Worker: registriert V4-6-Jobs via APScheduler.

Jobs:
  - SignalEvaluationJob:  täglich 06:00 Europe/Zurich
  - PaperLog fill_outcomes: täglich 06:15 Europe/Zurich
  - DriftMonitor:         täglich 06:30 Europe/Zurich
  - RetrainingJob:        monatlich, 1. des Monats 02:00 Europe/Zurich

Manueller Einmal-Lauf (ohne Scheduler, nützlich nach `alembic upgrade head`):
  python -m backend.infrastructure.workers.operations_worker --once

Dieser Befehl führt SignalEvaluationJob + PaperLog.fill_outcomes sofort aus und beendet sich.
Anschliessend kann der Scheduler-Worker live getestet werden (uvicorn ... --factory).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter
from backend.infrastructure.adapters.notification_adapter import send_email
from backend.infrastructure.adapters.operations_price_adapter import (
    EvalPriceAdapter,
    SymbolPriceAdapter,
)
from backend.infrastructure.persistence.session import get_session_factory

_logger = logging.getLogger(__name__)

_COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]
_ALERT_TO = "andrea.petretta@students.fhnw.ch"


async def _load_coin_map() -> dict[int, str]:
    """Lädt coin_id → symbol aus crypto_universe (nur aktive Coins)."""
    from sqlalchemy import text

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT coin_id, symbol FROM crypto_universe WHERE active = true")
        )
        return {row.coin_id: row.symbol for row in result}


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

    coin_map = await _load_coin_map()
    eval_price = EvalPriceAdapter(CryptoPriceAdapter(), coin_map)
    asof = date.today() - timedelta(days=1)
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        job = SignalEvaluationJob(
            outcome_repo=SQLASignalOutcomeRepository(session),
            metrics_repo=SQLALiveMetricsRepository(session),
            price_provider=eval_price,
        )
        result = await job.run(asof)
        _logger.info("SignalEvaluationJob abgeschlossen: %s", result)


async def _run_paper_log_outcomes() -> None:
    from backend.application.jobs.paper_trading_log import PaperTradingLogWriter
    from backend.infrastructure.persistence.repositories.paper_trading_log_repository import (
        SQLAPaperTradingLogRepository,
    )

    symbol_price = SymbolPriceAdapter(CryptoPriceAdapter())
    asof = date.today() - timedelta(days=1)
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        writer = PaperTradingLogWriter(
            repo=SQLAPaperTradingLogRepository(session),
            price_provider=symbol_price,
        )
        filled = await writer.fill_outcomes(asof)
        _logger.info("PaperLog.fill_outcomes abgeschlossen: filled=%d asof=%s", filled, asof)


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

    symbol_price = SymbolPriceAdapter(CryptoPriceAdapter())
    asof = date.today()
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        job = RetrainingJob(
            model_registry=SQLAModelRegistryRepository(session),
            price_provider=symbol_price,
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
        _run_paper_log_outcomes,
        trigger=CronTrigger(hour=6, minute=15),
        id="paper_log_outcomes_daily",
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


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Operations Worker — Einmal-Trigger für manuelle Verifikation"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="SignalEvaluationJob + PaperLog.fill_outcomes sofort ausführen und beenden",
    )
    args = parser.parse_args()

    if args.once:

        async def _run_once() -> None:
            _logger.info("--once: starte SignalEvaluationJob ...")
            await _run_signal_evaluation()
            _logger.info("--once: starte PaperLog.fill_outcomes ...")
            await _run_paper_log_outcomes()
            _logger.info("--once: fertig.")

        logging.basicConfig(level=logging.INFO)
        asyncio.run(_run_once())
    else:
        parser.print_help()
