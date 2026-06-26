"""DriftMonitor: vergleicht Live-Performance gegen Backtest-Erwartung.

Backtest-Benchmark-Werte (aus V4-1, BTC/ETH OOS-Ergebnisse):
  - expected_sharpe: 1.0 (konservativ, unterer Rand V4-1-Ergebnis)
  - expected_vol_mae: 0.3 (annualisiert)

Drift-Definition:
  - live_sharpe < expected_sharpe * (1 - SHARPE_THRESHOLD): 50% Abfall
  - vol_mae > expected_vol_mae * (1 + VOL_MAE_THRESHOLD): 50% Anstieg
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

_logger = logging.getLogger(__name__)

_SHARPE_THRESHOLD = 0.50
_VOL_MAE_THRESHOLD = 0.50
_EXPECTED_SHARPE = 1.0
_EXPECTED_VOL_MAE = 0.3


@dataclass
class DriftFlag:
    id: uuid.UUID
    coin: str | None
    flagged_at: datetime
    metric_name: str
    live_value: float
    expected_value: float
    pct_deviation: float
    is_active: bool
    alert_sent: bool


@dataclass
class LiveMetric:
    coin_id: int
    coin: str | None
    live_sharpe: float | None
    live_calmar: float | None
    vol_mae: float | None
    window_days: int
    n_signals: int


class DriftFlagRepository(Protocol):
    async def insert(self, flag: DriftFlag) -> None: ...

    async def list_active(self) -> list[DriftFlag]: ...

    async def mark_alert_sent(self, flag_id: uuid.UUID) -> None: ...


class MetricsProvider(Protocol):
    async def get_latest_metrics(self, window_days: int) -> list[LiveMetric]: ...


class AlertSender(Protocol):
    async def send_drift_alert(self, flags: list[DriftFlag]) -> None: ...


def _pct_dev(live: float, expected: float) -> float:
    if abs(expected) < 1e-10:
        return 0.0
    return (live - expected) / abs(expected)


class DriftMonitor:
    """Täglicher Drift-Check: vergleicht Live-Metriken gegen Backtest-Benchmark."""

    def __init__(
        self,
        flag_repo: DriftFlagRepository,
        metrics_provider: MetricsProvider,
        alert_sender: AlertSender,
        window_days: int = 90,
    ) -> None:
        self._flags = flag_repo
        self._metrics = metrics_provider
        self._alerts = alert_sender
        self._window = window_days

    async def run(self, asof: date) -> dict[str, int]:
        metrics = await self._metrics.get_latest_metrics(self._window)
        now = datetime.now(tz=UTC)
        new_flags: list[DriftFlag] = []

        for m in metrics:
            coin_label = m.coin or f"coin_id:{m.coin_id}"

            if m.live_sharpe is not None:
                threshold_val = _EXPECTED_SHARPE * (1 - _SHARPE_THRESHOLD)
                if m.live_sharpe < threshold_val:
                    pct = _pct_dev(m.live_sharpe, _EXPECTED_SHARPE)
                    flag = DriftFlag(
                        id=uuid.uuid4(),
                        coin=m.coin,
                        flagged_at=now,
                        metric_name="live_sharpe",
                        live_value=m.live_sharpe,
                        expected_value=_EXPECTED_SHARPE,
                        pct_deviation=pct,
                        is_active=True,
                        alert_sent=False,
                    )
                    new_flags.append(flag)
                    await self._flags.insert(flag)
                    _logger.warning(
                        "DRIFT: %s live_sharpe=%.3f (expected≥%.3f)",
                        coin_label,
                        m.live_sharpe,
                        threshold_val,
                    )

            if m.vol_mae is not None:
                threshold_val = _EXPECTED_VOL_MAE * (1 + _VOL_MAE_THRESHOLD)
                if m.vol_mae > threshold_val:
                    pct = _pct_dev(m.vol_mae, _EXPECTED_VOL_MAE)
                    flag = DriftFlag(
                        id=uuid.uuid4(),
                        coin=m.coin,
                        flagged_at=now,
                        metric_name="vol_mae",
                        live_value=m.vol_mae,
                        expected_value=_EXPECTED_VOL_MAE,
                        pct_deviation=pct,
                        is_active=True,
                        alert_sent=False,
                    )
                    new_flags.append(flag)
                    await self._flags.insert(flag)
                    _logger.warning(
                        "DRIFT: %s vol_mae=%.3f (expected≤%.3f)",
                        coin_label,
                        m.vol_mae,
                        threshold_val,
                    )

        if new_flags:
            await self._alerts.send_drift_alert(new_flags)

        return {"new_flags": len(new_flags)}
