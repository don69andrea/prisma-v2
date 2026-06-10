"""Background-Worker für tägliche Alert-Prüfung via APScheduler."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.application.services.alert_service import AlertService
from backend.infrastructure.persistence.repositories.alert_repository import SQLAAlertRepository
from backend.infrastructure.persistence.session import get_session_factory

_logger = logging.getLogger(__name__)


async def _run_alert_check() -> None:
    """Wird täglich durch APScheduler aufgerufen."""
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        service = AlertService(alert_repo=SQLAAlertRepository(session=session))
        triggered = await service.check_and_notify()
        _logger.info("Alert Worker: %d Alerts ausgelöst", triggered)


def create_alert_scheduler() -> AsyncIOScheduler:
    """Erstellt APScheduler mit täglichem Alert-Job (08:00 Europe/Zurich)."""
    scheduler = AsyncIOScheduler(timezone="Europe/Zurich")
    scheduler.add_job(
        _run_alert_check,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_alert_check",
        replace_existing=True,
    )
    return scheduler
