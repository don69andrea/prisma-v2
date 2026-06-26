"""Unit-Tests für DriftMonitor (V4-6).

Pflicht-Guards:
  - Drift-Alert feuert wenn live_sharpe künstlich unter Threshold gesetzt
  - Kein Alert wenn live_sharpe OK
  - Vol-MAE-Drift feuert bei hohem vol_mae
  - Kein Alert wenn keine Metriken
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from backend.application.jobs.drift_monitor import (
    DriftFlag,
    DriftMonitor,
    LiveMetric,
    _pct_dev,
)

pytestmark = pytest.mark.unit


# ── Stubs ──────────────────────────────────────────────────────────────────────


class StubDriftFlagRepo:
    def __init__(self) -> None:
        self.inserted: list[DriftFlag] = []

    async def insert(self, flag: DriftFlag) -> None:
        self.inserted.append(flag)

    async def list_active(self) -> list[DriftFlag]:
        return self.inserted

    async def mark_alert_sent(self, flag_id: uuid.UUID) -> None:
        pass


class StubMetricsProvider:
    def __init__(self, metrics: list[LiveMetric]) -> None:
        self._metrics = metrics

    async def get_latest_metrics(self, window_days: int) -> list[LiveMetric]:
        return self._metrics


class StubAlertSender:
    def __init__(self) -> None:
        self.sent: list[DriftFlag] = []

    async def send_drift_alert(self, flags: list[DriftFlag]) -> None:
        self.sent.extend(flags)


def _metric(
    coin: str = "BTC-USD",
    live_sharpe: float | None = None,
    live_calmar: float | None = None,
    vol_mae: float | None = None,
) -> LiveMetric:
    return LiveMetric(
        coin_id=1,
        coin=coin,
        live_sharpe=live_sharpe,
        live_calmar=live_calmar,
        vol_mae=vol_mae,
        window_days=90,
        n_signals=50,
    )


# ── Drift Sharpe Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_drift_alert_fires_on_low_sharpe() -> None:
    """Alert feuert wenn live_sharpe weit unter Erwartung (0.1 < 0.5 threshold)."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([_metric(live_sharpe=0.1)]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] >= 1
    assert len(alert_sender.sent) >= 1
    sharpe_flags = [f for f in flag_repo.inserted if f.metric_name == "live_sharpe"]
    assert len(sharpe_flags) == 1
    assert sharpe_flags[0].live_value == 0.1
    assert sharpe_flags[0].expected_value == 1.0


@pytest.mark.asyncio
async def test_no_alert_when_sharpe_ok() -> None:
    """Kein Alert wenn live_sharpe über dem Threshold (0.6 > 0.5)."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([_metric(live_sharpe=0.6)]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] == 0
    assert len(alert_sender.sent) == 0
    assert len(flag_repo.inserted) == 0


@pytest.mark.asyncio
async def test_no_alert_when_sharpe_is_none() -> None:
    """Kein Alert wenn live_sharpe is None."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([_metric(live_sharpe=None)]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] == 0


# ── Drift Vol MAE Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_drift_alert_fires_on_high_vol_mae() -> None:
    """Alert feuert wenn vol_mae über dem Threshold (0.5 > 0.3 * 1.5 = 0.45)."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([_metric(vol_mae=0.50)]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] >= 1
    vol_flags = [f for f in flag_repo.inserted if f.metric_name == "vol_mae"]
    assert len(vol_flags) == 1
    assert vol_flags[0].live_value == 0.50


@pytest.mark.asyncio
async def test_no_alert_when_vol_mae_ok() -> None:
    """Kein Alert wenn vol_mae unter dem Threshold (0.2 < 0.45)."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([_metric(vol_mae=0.20)]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] == 0


# ── Multiple Metrics ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_both_flags_fire_simultaneously() -> None:
    """Sowohl sharpe als auch vol_mae können im gleichen Lauf feuern."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([_metric(live_sharpe=0.05, vol_mae=0.80)]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] == 2
    metric_names = {f.metric_name for f in flag_repo.inserted}
    assert "live_sharpe" in metric_names
    assert "vol_mae" in metric_names


@pytest.mark.asyncio
async def test_no_alert_when_no_metrics() -> None:
    """Kein Alert wenn keine Metriken vorhanden."""
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider([]),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] == 0
    assert len(alert_sender.sent) == 0


@pytest.mark.asyncio
async def test_multiple_coins_independent_flags() -> None:
    """Verschiedene Coins bekommen unabhängige Flags."""
    metrics = [
        _metric(coin="BTC-USD", live_sharpe=0.05),
        _metric(coin="ETH-USD", live_sharpe=0.8),  # OK
    ]
    flag_repo = StubDriftFlagRepo()
    alert_sender = StubAlertSender()
    monitor = DriftMonitor(
        flag_repo=flag_repo,
        metrics_provider=StubMetricsProvider(metrics),
        alert_sender=alert_sender,
    )

    result = await monitor.run(asof=date(2026, 1, 10))

    assert result["new_flags"] == 1
    assert flag_repo.inserted[0].coin == "BTC-USD"


# ── _pct_dev ──────────────────────────────────────────────────────────────────


def test_pct_dev_positive_deviation() -> None:
    assert abs(_pct_dev(1.5, 1.0) - 0.5) < 1e-9


def test_pct_dev_negative_deviation() -> None:
    assert abs(_pct_dev(0.5, 1.0) - (-0.5)) < 1e-9


def test_pct_dev_zero_expected() -> None:
    assert _pct_dev(1.0, 0.0) == 0.0
