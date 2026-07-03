"""Alert Service — CRUD und tägliche Alert-Prüfung."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.domain.entities.alert import Alert
from backend.domain.repositories.alert_repository import AlertRepository
from backend.infrastructure.adapters.notification_adapter import send_email, send_webhook

_logger = logging.getLogger(__name__)


class AlertService:
    """Verwaltet Alerts und führt die tägliche Prüfung durch.

    yfinance_adapter und signal_service sind optional (Any | None) damit
    der Service auf develop ohne ML-Layer-PRs lauffähig ist.
    """

    def __init__(
        self,
        alert_repo: AlertRepository,
        yfinance_adapter: Any | None = None,
        signal_service: Any | None = None,
    ) -> None:
        self._repo = alert_repo
        self._yf = yfinance_adapter
        self._signal_svc = signal_service

    # --- CRUD ---

    async def create_alert(
        self,
        user_id: UUID,
        ticker: str,
        trigger_type: str,
        threshold: float,
        channel: str,
        target: str,
        current_price: float | None = None,
        current_signal: str | None = None,
    ) -> Alert:
        alert = Alert(
            id=uuid4(),
            user_id=user_id,
            ticker=ticker.upper(),
            trigger_type=trigger_type,  # type: ignore[arg-type]
            threshold=threshold,
            channel=channel,  # type: ignore[arg-type]
            target=target,
            is_active=True,
            created_at=datetime.now(tz=UTC),
            last_triggered_at=None,
            last_signal=current_signal,
            baseline_price=current_price,
        )
        await self._repo.save(alert)
        return alert

    async def list_alerts(self, user_id: UUID, target: str | None = None) -> list[Alert]:
        """Listet ausschließlich Alerts des angegebenen Nutzers (Mandanten-Isolation).

        ``target`` filtert optional zusätzlich innerhalb der eigenen Alerts.
        """
        alerts = await self._repo.list_by_user(user_id)
        if target:
            alerts = [a for a in alerts if a.target == target]
        return alerts

    async def delete_alert(self, alert_id: UUID, user_id: UUID) -> bool:
        """Löscht einen Alert nur, wenn er dem Nutzer gehört.

        Gibt False zurück (→ 404), wenn der Alert nicht existiert *oder* einem
        anderen Nutzer gehört — die Existenz fremder Alerts wird nicht geleakt.
        """
        alert = await self._repo.get_by_id(alert_id)
        if alert is None or alert.user_id != user_id:
            return False
        await self._repo.delete(alert_id)
        return True

    # --- Tägliche Prüfung ---

    async def check_and_notify(self) -> int:
        """Prüft alle aktiven Alerts und sendet Benachrichtigungen.

        Gibt Anzahl ausgelöster Alerts zurück.
        """
        alerts = await self._repo.list_active()
        triggered = 0
        for alert in alerts:
            try:
                fired = await self._check_alert(alert)
                if fired:
                    triggered += 1
            except Exception:
                _logger.exception("Alert-Check fehlgeschlagen für %s", alert.id)
        _logger.info("Alert-Check abgeschlossen: %d/%d ausgelöst", triggered, len(alerts))
        return triggered

    async def _check_alert(self, alert: Alert) -> bool:
        if alert.trigger_type == "PRICE_CHANGE":
            return await self._check_price_alert(alert)
        return await self._check_signal_alert(alert)

    async def _check_price_alert(self, alert: Alert) -> bool:
        if self._yf is None or alert.baseline_price is None:
            return False
        try:
            current = await self._yf.get_current_price(alert.ticker)
        except Exception as exc:
            _logger.warning(
                "Preis-Check für Alert %s (%s) fehlgeschlagen: %s", alert.id, alert.ticker, exc
            )
            return False
        if current is None:
            return False
        pct_change = abs(current - alert.baseline_price) / alert.baseline_price * 100
        if pct_change < alert.threshold:
            return False
        direction = "gestiegen" if current > alert.baseline_price else "gefallen"
        msg = (
            f"PRISMA Alert: {alert.ticker} ist um {pct_change:.1f}% {direction} "
            f"(Baseline: {alert.baseline_price:.2f}, Aktuell: {current:.2f})"
        )
        await self._notify(alert, msg)
        updated = Alert(
            id=alert.id,
            user_id=alert.user_id,
            ticker=alert.ticker,
            trigger_type=alert.trigger_type,
            threshold=alert.threshold,
            channel=alert.channel,
            target=alert.target,
            is_active=alert.is_active,
            created_at=alert.created_at,
            last_triggered_at=datetime.now(tz=UTC),
            last_signal=alert.last_signal,
            baseline_price=current,
        )
        await self._repo.update(updated)
        return True

    async def _check_signal_alert(self, alert: Alert) -> bool:
        if self._signal_svc is None:
            return False
        try:
            new_signal = await self._signal_svc.get_current_signal(alert.ticker)
        except Exception as exc:
            _logger.warning(
                "Signal-Check für Alert %s (%s) fehlgeschlagen: %s", alert.id, alert.ticker, exc
            )
            return False
        if new_signal is None or new_signal == alert.last_signal:
            return False
        msg = (
            f"PRISMA Alert: {alert.ticker} Signal geändert "
            f"von {alert.last_signal or 'unbekannt'} zu {new_signal}"
        )
        await self._notify(alert, msg)
        updated = Alert(
            id=alert.id,
            user_id=alert.user_id,
            ticker=alert.ticker,
            trigger_type=alert.trigger_type,
            threshold=alert.threshold,
            channel=alert.channel,
            target=alert.target,
            is_active=alert.is_active,
            created_at=alert.created_at,
            last_triggered_at=datetime.now(tz=UTC),
            last_signal=new_signal,
            baseline_price=alert.baseline_price,
        )
        await self._repo.update(updated)
        return True

    async def _notify(self, alert: Alert, message: str) -> None:
        if alert.channel == "EMAIL":
            await send_email(
                to=alert.target,
                subject=f"PRISMA Alert: {alert.ticker}",
                body=message,
            )
        else:
            await send_webhook(
                url=alert.target,
                payload={"ticker": alert.ticker, "message": message},
            )
