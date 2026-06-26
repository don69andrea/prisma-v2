"""Unit-Tests für SignalEvaluationJob (V4-6).

Pflicht-Guards:
  - Look-Ahead: pending outcome noch nicht fällig → KEIN Nachtrag
  - Look-Ahead: fälliges outcome → WIRD nachgetragen, Preis korrekt berechnet
  - Hit-Rate-Berechnung korrekt
  - Vol-MAE-Berechnung korrekt
  - Keine Verarbeitung wenn Preis fehlt
  - Metriken werden nur für Coins mit resolved records geschrieben
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from backend.application.jobs.signal_evaluation_job import (
    MetricsRecord,
    OutcomeRecord,
    SignalEvaluationJob,
    _compute_metrics,
    _compute_vol_mae,
)

pytestmark = pytest.mark.unit


# ── Stubs ──────────────────────────────────────────────────────────────────────


class StubOutcomeRepo:
    def __init__(self, records: list[OutcomeRecord]) -> None:
        self._records = list(records)
        self.backfilled: dict[tuple[int, date, int], float] = {}

    async def list_pending(self, asof: date) -> list[OutcomeRecord]:
        return [r for r in self._records if r.realized_fwd_return is None]

    async def backfill_return(
        self, coin_id: int, signal_date: date, horizon: int, realized: float
    ) -> None:
        self.backfilled[(coin_id, signal_date, horizon)] = realized
        for r in self._records:
            if r.coin_id == coin_id and r.signal_date == signal_date and r.horizon == horizon:
                object.__setattr__(r, "realized_fwd_return", realized)

    async def list_resolved(self, coin_id: int, since: date) -> list[OutcomeRecord]:
        return [
            r
            for r in self._records
            if (
                r.coin_id == coin_id
                and r.signal_date >= since
                and r.realized_fwd_return is not None
            )
        ]


class StubPriceProvider:
    def __init__(self, prices: dict[tuple[int, date], float]) -> None:
        self._prices = prices

    async def get_close(self, coin_id: int, asof: date) -> float | None:
        return self._prices.get((coin_id, asof))


class StubMetricsRepo:
    def __init__(self) -> None:
        self.inserted: list[MetricsRecord] = []

    async def insert(self, record: MetricsRecord, computed_at: object) -> None:
        self.inserted.append(record)


def _make_record(
    coin_id: int = 1,
    signal_date: date = date(2026, 1, 10),
    horizon: int = 1,
    action: str = "BUY",
    realized_fwd_return: float | None = None,
    pred_vol: float | None = 0.3,
) -> OutcomeRecord:
    return OutcomeRecord(
        coin_id=coin_id,
        signal_date=signal_date,
        horizon=horizon,
        action=action,
        size_factor=0.5,
        confidence=0.7,
        pred_vol=pred_vol,
        realized_fwd_return=realized_fwd_return,
    )


# ── Look-Ahead-Guard ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_look_ahead_guard_not_due_yet() -> None:
    """Pending outcome mit horizon=1 und signal_date=asof wird NICHT nachgetragen."""
    asof = date(2026, 1, 10)
    rec = _make_record(signal_date=asof, horizon=1)
    prices = {(1, asof): 100.0, (1, asof + timedelta(days=1)): 105.0}
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 0
    assert (1, asof, 1) not in outcome_repo.backfilled


@pytest.mark.asyncio
async def test_look_ahead_guard_now_due() -> None:
    """Pending outcome mit signal_date=yesterday wird korrekt nachgetragen."""
    asof = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    rec = _make_record(signal_date=yesterday, horizon=1)
    prices = {(1, yesterday): 100.0, (1, asof): 105.0}
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 1
    assert abs(outcome_repo.backfilled[(1, yesterday, 1)] - 0.05) < 1e-9


@pytest.mark.asyncio
async def test_look_ahead_horizon_5_not_due_after_3_days() -> None:
    """horizon=5, asof=signal_date+3 → outcome_date=signal_date+5 > asof → kein Nachtrag."""
    signal_date = date(2026, 1, 1)
    asof = signal_date + timedelta(days=3)
    rec = _make_record(signal_date=signal_date, horizon=5)
    prices = {(1, signal_date): 100.0, (1, signal_date + timedelta(days=5)): 110.0}
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 0


@pytest.mark.asyncio
async def test_look_ahead_horizon_5_exactly_due() -> None:
    """horizon=5, asof=signal_date+5 → outcome_date == asof → WIRD nachgetragen."""
    signal_date = date(2026, 1, 1)
    asof = signal_date + timedelta(days=5)
    rec = _make_record(signal_date=signal_date, horizon=5)
    prices = {(1, signal_date): 200.0, (1, asof): 220.0}
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 1
    assert abs(outcome_repo.backfilled[(1, signal_date, 5)] - 0.10) < 1e-9


# ── Preis-Fehler ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_backfill_when_signal_price_missing() -> None:
    """Kein Nachtrag wenn Preis am Signal-Tag fehlt."""
    asof = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    rec = _make_record(signal_date=yesterday, horizon=1)
    prices: dict[tuple[int, date], float] = {(1, asof): 105.0}  # signal price missing
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 0


@pytest.mark.asyncio
async def test_no_backfill_when_outcome_price_missing() -> None:
    """Kein Nachtrag wenn Preis am Outcome-Tag fehlt."""
    asof = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    rec = _make_record(signal_date=yesterday, horizon=1)
    prices: dict[tuple[int, date], float] = {(1, yesterday): 100.0}  # outcome price missing
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 0


# ── _compute_metrics ───────────────────────────────────────────────────────────


def test_compute_metrics_empty() -> None:
    result = _compute_metrics([])
    assert result["hit_rate"] is None
    assert result["live_sharpe"] is None
    assert result["live_calmar"] is None


def test_compute_metrics_no_buy_records() -> None:
    records = [_make_record(action="HOLD", realized_fwd_return=0.02)]
    result = _compute_metrics(records)
    assert result["hit_rate"] is None


def test_compute_metrics_single_buy() -> None:
    rec = _make_record(action="BUY", realized_fwd_return=0.05)
    result = _compute_metrics([rec])
    assert result["hit_rate"] == 1.0
    assert result["live_sharpe"] is None  # need ≥ 2 records for std


def test_compute_metrics_hit_rate() -> None:
    records = [
        _make_record(action="BUY", realized_fwd_return=0.05),
        _make_record(action="BUY", realized_fwd_return=0.03),
        _make_record(action="BUY", realized_fwd_return=-0.02),
    ]
    result = _compute_metrics(records)
    assert abs(result["hit_rate"] - 2 / 3) < 1e-9  # type: ignore[operator]


def test_compute_metrics_sharpe_positive() -> None:
    records = [_make_record(action="BUY", realized_fwd_return=r) for r in [0.01, 0.02, 0.03]]
    result = _compute_metrics(records)
    assert result["live_sharpe"] is not None
    assert result["live_sharpe"] > 0


def test_compute_metrics_calmar_with_drawdown() -> None:
    returns = [0.10, -0.20, 0.05, 0.08]
    records = [_make_record(action="BUY", realized_fwd_return=r) for r in returns]
    result = _compute_metrics(records)
    assert result["live_calmar"] is not None


# ── _compute_vol_mae ──────────────────────────────────────────────────────────


def test_compute_vol_mae_empty() -> None:
    assert _compute_vol_mae([]) is None


def test_compute_vol_mae_no_pred_vol() -> None:
    rec = _make_record(realized_fwd_return=0.05, pred_vol=None)
    assert _compute_vol_mae([rec]) is None


def test_compute_vol_mae_correct() -> None:
    rec = _make_record(realized_fwd_return=0.01, pred_vol=0.5)
    result = _compute_vol_mae([rec])
    assert result is not None
    realized_vol = float(np.sqrt(0.01**2 * 252.0))
    expected_mae = abs(0.5 - realized_vol)
    assert abs(result - expected_mae) < 1e-9


# ── Metrics written ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_written_when_resolved_records_exist() -> None:
    """Nach Nachtrag werden live_performance_metrics geschrieben."""
    asof = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    rec = _make_record(coin_id=1, signal_date=yesterday, horizon=1, action="BUY")
    prices = {(1, yesterday): 100.0, (1, asof): 102.0}
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["backfilled"] == 1
    assert result["metrics_written"] > 0
    assert len(metrics_repo.inserted) > 0
    assert metrics_repo.inserted[0].coin_id == 1


@pytest.mark.asyncio
async def test_metrics_not_written_when_no_resolved_records() -> None:
    """Keine Metriken wenn keine resolved records vorhanden."""
    asof = date(2026, 1, 10)
    rec = _make_record(coin_id=1, signal_date=asof, horizon=1)  # not due
    prices: dict[tuple[int, date], float] = {}
    outcome_repo = StubOutcomeRepo([rec])
    metrics_repo = StubMetricsRepo()
    job = SignalEvaluationJob(outcome_repo, metrics_repo, StubPriceProvider(prices))

    result = await job.run(asof=asof)

    assert result["metrics_written"] == 0
    assert len(metrics_repo.inserted) == 0
