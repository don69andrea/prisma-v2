"""Unit-Tests für AlertService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.application.services.alert_service import AlertService
from backend.domain.entities.alert import Alert


def _make_alert(
    trigger_type: str = "PRICE_CHANGE",
    threshold: float = 5.0,
    channel: str = "EMAIL",
    last_signal: str | None = None,
    baseline_price: float | None = 100.0,
) -> Alert:
    return Alert(
        id=uuid4(),
        ticker="NESN",
        trigger_type=trigger_type,  # type: ignore[arg-type]
        threshold=threshold,
        channel=channel,  # type: ignore[arg-type]
        target="test@example.com",
        is_active=True,
        created_at=datetime.now(tz=UTC),
        last_triggered_at=None,
        last_signal=last_signal,
        baseline_price=baseline_price,
    )


# --- create_alert ---


@pytest.mark.asyncio
async def test_create_alert_saves_and_returns() -> None:
    repo = AsyncMock()
    service = AlertService(alert_repo=repo)
    alert = await service.create_alert(
        ticker="NESN",
        trigger_type="SIGNAL_CHANGE",
        threshold=0.0,
        channel="EMAIL",
        target="user@example.com",
    )
    assert alert.ticker == "NESN"
    assert alert.is_active is True
    repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_create_alert_normalises_ticker() -> None:
    repo = AsyncMock()
    service = AlertService(alert_repo=repo)
    alert = await service.create_alert(
        ticker="nesn", trigger_type="PRICE_CHANGE", threshold=5.0, channel="EMAIL", target="x@y.com"
    )
    assert alert.ticker == "NESN"


# --- list_alerts ---


@pytest.mark.asyncio
async def test_list_alerts_with_target_filters() -> None:
    repo = AsyncMock()
    repo.list_by_owner.return_value = [_make_alert()]
    service = AlertService(alert_repo=repo)
    result = await service.list_alerts(target="test@example.com")
    repo.list_by_owner.assert_called_once_with("test@example.com")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_alerts_without_target_returns_active() -> None:
    repo = AsyncMock()
    repo.list_active.return_value = [_make_alert(), _make_alert()]
    service = AlertService(alert_repo=repo)
    result = await service.list_alerts()
    repo.list_active.assert_called_once()
    assert len(result) == 2


# --- delete_alert ---


@pytest.mark.asyncio
async def test_delete_alert_returns_true_if_found() -> None:
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_alert()
    service = AlertService(alert_repo=repo)
    aid = uuid4()
    result = await service.delete_alert(aid)
    assert result is True
    repo.delete.assert_called_once_with(aid)


@pytest.mark.asyncio
async def test_delete_alert_returns_false_if_not_found() -> None:
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    service = AlertService(alert_repo=repo)
    result = await service.delete_alert(uuid4())
    assert result is False
    repo.delete.assert_not_called()


# --- check_and_notify: PRICE_CHANGE ---


@pytest.mark.asyncio
async def test_price_alert_fires_when_threshold_exceeded() -> None:
    repo = AsyncMock()
    alert = _make_alert(trigger_type="PRICE_CHANGE", threshold=5.0, baseline_price=100.0)
    repo.list_active.return_value = [alert]

    yf = AsyncMock()
    yf.get_current_price.return_value = 110.0  # +10% → über 5% Schwelle

    service = AlertService(alert_repo=repo, yfinance_adapter=yf)
    with patch(
        "backend.application.services.alert_service.send_email", new_callable=AsyncMock
    ) as mock_email:
        triggered = await service.check_and_notify()

    assert triggered == 1
    mock_email.assert_called_once()
    repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_price_alert_does_not_fire_below_threshold() -> None:
    repo = AsyncMock()
    alert = _make_alert(trigger_type="PRICE_CHANGE", threshold=10.0, baseline_price=100.0)
    repo.list_active.return_value = [alert]

    yf = AsyncMock()
    yf.get_current_price.return_value = 104.0  # +4% → unter 10% Schwelle

    service = AlertService(alert_repo=repo, yfinance_adapter=yf)
    triggered = await service.check_and_notify()
    assert triggered == 0
    repo.update.assert_not_called()


# --- check_and_notify: SIGNAL_CHANGE ---


@pytest.mark.asyncio
async def test_signal_alert_fires_on_change() -> None:
    repo = AsyncMock()
    alert = _make_alert(trigger_type="SIGNAL_CHANGE", last_signal="HOLD")
    repo.list_active.return_value = [alert]

    signal_svc = AsyncMock()
    signal_svc.get_current_signal.return_value = "BUY"

    service = AlertService(alert_repo=repo, signal_service=signal_svc)
    with patch(
        "backend.application.services.alert_service.send_email", new_callable=AsyncMock
    ) as mock_email:
        triggered = await service.check_and_notify()

    assert triggered == 1
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_signal_alert_does_not_fire_if_unchanged() -> None:
    repo = AsyncMock()
    alert = _make_alert(trigger_type="SIGNAL_CHANGE", last_signal="BUY")
    repo.list_active.return_value = [alert]

    signal_svc = AsyncMock()
    signal_svc.get_current_signal.return_value = "BUY"

    service = AlertService(alert_repo=repo, signal_service=signal_svc)
    triggered = await service.check_and_notify()
    assert triggered == 0


@pytest.mark.asyncio
async def test_check_and_notify_no_adapters_returns_zero() -> None:
    """Ohne yf/signal Adapter: kein Alert feuert (kein Crash)."""
    repo = AsyncMock()
    repo.list_active.return_value = [
        _make_alert("PRICE_CHANGE"),
        _make_alert("SIGNAL_CHANGE"),
    ]
    service = AlertService(alert_repo=repo)
    triggered = await service.check_and_notify()
    assert triggered == 0
