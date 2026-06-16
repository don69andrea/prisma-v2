"""Background-Worker für tägliche Alert-Prüfung via APScheduler."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.application.services.alert_service import AlertService
from backend.application.services.signal_aggregation_service import SignalAggregationService
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.infrastructure.persistence.repositories.alert_repository import SQLAAlertRepository
from backend.infrastructure.persistence.session import get_session_factory

_logger = logging.getLogger(__name__)


class _YFinancePriceAdapter:
    """Thin wrapper um YFinanceSwissAdapter, der get_current_price() exponiert.

    AlertService erwartet einen Adapter mit ``async get_current_price(ticker) -> float | None``.
    YFinanceSwissAdapter stellt diese Methode nicht direkt bereit — der aktuelle
    Preis wird daher aus dem letzten Close-Wert der Preis-Historie abgeleitet.
    """

    def __init__(self, adapter: YFinanceSwissAdapter) -> None:
        self._adapter = adapter

    async def get_current_price(self, ticker: str) -> float | None:
        try:
            df = await self._adapter.get_price_history(ticker, days=2)
            if df.empty or "Close" not in df.columns:
                return None
            return float(df["Close"].iloc[-1])
        except Exception as exc:
            _logger.warning("Preis-Abruf für %s fehlgeschlagen: %s", ticker, exc)
            return None


class _SignalServiceAdapter:
    """Thin wrapper um SignalAggregationService, der get_current_signal() exponiert.

    AlertService erwartet ``async get_current_signal(ticker) -> str | None``.
    SignalAggregationService liefert ein DecisionSignal-Objekt; dieser Adapter
    extrahiert daraus das Signal-Label (z.B. 'BUY', 'HOLD', 'SELL').
    """

    def __init__(self, signal_service: SignalAggregationService) -> None:
        self._svc = signal_service

    async def get_current_signal(self, ticker: str) -> str | None:
        try:
            result = await self._svc.get_signal(ticker)
            if result is None:
                return None
            return result.signal
        except Exception as exc:
            _logger.warning("Signal-Abruf für %s fehlgeschlagen: %s", ticker, exc)
            return None


# Prozess-weite Singletons — YFinanceSwissAdapter öffnet keinen Connection-Pool,
# aber Wiederverwendung vermeidet unnötigen Objekt-Overhead bei häufigen Cron-Läufen.
_yfinance_adapter: _YFinancePriceAdapter | None = None
_signal_adapter: _SignalServiceAdapter | None = None


def _get_yfinance_price_adapter() -> _YFinancePriceAdapter:
    global _yfinance_adapter
    if _yfinance_adapter is None:
        _yfinance_adapter = _YFinancePriceAdapter(YFinanceSwissAdapter())
    return _yfinance_adapter


def _get_signal_adapter() -> _SignalServiceAdapter:
    global _signal_adapter
    if _signal_adapter is None:
        _signal_adapter = _SignalServiceAdapter(SignalAggregationService())
    return _signal_adapter


async def _run_alert_check() -> None:
    """Wird täglich durch APScheduler aufgerufen."""
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        service = AlertService(
            alert_repo=SQLAAlertRepository(session=session),
            yfinance_adapter=_get_yfinance_price_adapter(),
            signal_service=_get_signal_adapter(),
        )
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
