"""SignalEvaluationJob: täglicher Job zum Nachtragen realisierter Signal-Outcomes.

Look-Ahead-Guard (PFLICHT): Outcomes werden AUSSCHLIESSLICH nachgetragen wenn
signal_date + horizon <= asof (d.h. die Zukunft ist bekannt). Wir lesen niemals
Daten nach asof.

Metriken:
  - hit_rate: Anteil BUY-Signale mit realized_fwd_return > 0
  - live_sharpe: annualisierter Sharpe der realisierten Returns (BUY-Signale)
  - live_calmar: |mean_return / max_drawdown|
  - vol_mae: Mean-Absolute-Error zwischen pred_vol und sqrt(realized_fwd_return^2 * 252)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

import numpy as np

_logger = logging.getLogger(__name__)

_WINDOW_DAYS = [90, 180]
_ANN_FACTOR = 252.0


@dataclass
class OutcomeRecord:
    coin_id: int
    signal_date: date
    horizon: int
    action: str
    size_factor: float
    confidence: float
    pred_vol: float | None
    realized_fwd_return: float | None


@dataclass
class MetricsRecord:
    coin_id: int
    window_days: int
    n_signals: int
    hit_rate: float | None
    live_sharpe: float | None
    live_calmar: float | None
    vol_mae: float | None


class SignalOutcomeRepository(Protocol):
    async def list_pending(self, asof: date) -> list[OutcomeRecord]: ...

    async def backfill_return(
        self, coin_id: int, signal_date: date, horizon: int, realized: float
    ) -> None: ...

    async def list_resolved(self, coin_id: int, since: date) -> list[OutcomeRecord]: ...


class LiveMetricsRepository(Protocol):
    async def insert(self, record: MetricsRecord, computed_at: object) -> None: ...


class PriceProvider(Protocol):
    async def get_close(self, coin_id: int, asof: date) -> float | None: ...


def _compute_metrics(records: list[OutcomeRecord]) -> dict[str, float | None]:
    buy_records = [r for r in records if r.action == "BUY" and r.realized_fwd_return is not None]
    if not buy_records:
        return {"hit_rate": None, "live_sharpe": None, "live_calmar": None}

    returns = np.array([r.realized_fwd_return for r in buy_records], dtype=float)
    hit_rate = float(np.mean(returns > 0))

    if len(returns) < 2:
        return {"hit_rate": hit_rate, "live_sharpe": None, "live_calmar": None}

    mean_r = float(np.mean(returns))
    std_r = float(np.std(returns, ddof=1))
    live_sharpe = float(mean_r / std_r * np.sqrt(_ANN_FACTOR)) if std_r > 0 else None

    cum = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cum)
    drawdowns = (cum - running_max) / running_max
    max_dd = float(np.min(drawdowns))
    live_calmar = float(mean_r * _ANN_FACTOR / abs(max_dd)) if max_dd < 0 else None

    return {"hit_rate": hit_rate, "live_sharpe": live_sharpe, "live_calmar": live_calmar}


def _compute_vol_mae(records: list[OutcomeRecord]) -> float | None:
    rows = [r for r in records if r.pred_vol is not None and r.realized_fwd_return is not None]
    if not rows:
        return None
    realized_vols = np.sqrt(np.array([r.realized_fwd_return for r in rows]) ** 2 * _ANN_FACTOR)
    pred_vols = np.array([r.pred_vol for r in rows], dtype=float)
    return float(np.mean(np.abs(pred_vols - realized_vols)))


class SignalEvaluationJob:
    """Täglicher Auswertungs-Job: füllt realized_fwd_return nach und berechnet Live-Metriken."""

    def __init__(
        self,
        outcome_repo: SignalOutcomeRepository,
        metrics_repo: LiveMetricsRepository,
        price_provider: PriceProvider,
    ) -> None:
        self._outcomes = outcome_repo
        self._metrics = metrics_repo
        self._prices = price_provider

    async def run(self, asof: date) -> dict[str, int]:
        """Führt den Job für den gegebenen Stichtag aus.

        Returns dict with keys: backfilled, metrics_written.
        """
        pending = await self._outcomes.list_pending(asof)
        backfilled = 0
        for rec in pending:
            # Look-Ahead-Guard: nur nachtragen wenn signal_date + horizon <= asof
            outcome_date = rec.signal_date + timedelta(days=rec.horizon)
            if outcome_date > asof:
                continue

            price_at_signal = await self._prices.get_close(rec.coin_id, rec.signal_date)
            price_at_outcome = await self._prices.get_close(rec.coin_id, outcome_date)

            if price_at_signal is None or price_at_outcome is None or price_at_signal <= 0:
                _logger.warning(
                    "Kein Preis für coin_id=%d signal=%s outcome=%s",
                    rec.coin_id,
                    rec.signal_date,
                    outcome_date,
                )
                continue

            fwd_return = price_at_outcome / price_at_signal - 1.0
            await self._outcomes.backfill_return(
                rec.coin_id, rec.signal_date, rec.horizon, fwd_return
            )
            backfilled += 1

        # Metriken berechnen: alle einzigartigen Coins
        coin_ids = {r.coin_id for r in pending}
        metrics_written = 0
        computed_at = datetime.now(tz=UTC)

        for coin_id in coin_ids:
            for window in _WINDOW_DAYS:
                since = asof - timedelta(days=window)
                resolved = await self._outcomes.list_resolved(coin_id, since)
                if not resolved:
                    continue
                stats = _compute_metrics(resolved)
                vol_mae = _compute_vol_mae(resolved)
                record = MetricsRecord(
                    coin_id=coin_id,
                    window_days=window,
                    n_signals=len(resolved),
                    hit_rate=stats.get("hit_rate"),
                    live_sharpe=stats.get("live_sharpe"),
                    live_calmar=stats.get("live_calmar"),
                    vol_mae=vol_mae,
                )
                await self._metrics.insert(record, computed_at)
                metrics_written += 1

        _logger.info("SignalEvaluationJob: backfilled=%d, metrics=%d", backfilled, metrics_written)
        return {"backfilled": backfilled, "metrics_written": metrics_written}
