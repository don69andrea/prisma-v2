"""Unit-Tests für PaperTradingLogWriter (V4-6b).

Pflicht-Guards:
  - log_signals schreibt korrekte Anzahl Einträge
  - fill_outcomes respektiert Look-Ahead (Datum noch nicht fällig → kein Nachtrag)
  - fill_outcomes trägt nach wenn Datum fällig
  - Append-only: jeder Eintrag bekommt neue UUID
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from backend.application.jobs.paper_trading_log import (
    LiveSignal,
    PaperLogEntry,
    PaperTradingLogWriter,
)

pytestmark = pytest.mark.unit


# ── Stubs ──────────────────────────────────────────────────────────────────────


class StubPaperLogRepo:
    def __init__(self, entries: list[PaperLogEntry] | None = None) -> None:
        self.entries: list[PaperLogEntry] = list(entries or [])
        self.backfilled: dict[uuid.UUID, float] = {}

    async def insert(self, entry: PaperLogEntry) -> None:
        self.entries.append(entry)

    async def list_pending_outcomes(self, asof: date) -> list[PaperLogEntry]:
        return [e for e in self.entries if e.realized_fwd_return is None]

    async def backfill_return(self, entry_id: uuid.UUID, realized: float) -> None:
        self.backfilled[entry_id] = realized

    async def list_all(
        self, coin: str | None = None, since: date | None = None
    ) -> list[PaperLogEntry]:
        result = self.entries
        if coin is not None:
            result = [e for e in result if e.coin == coin]
        if since is not None:
            result = [e for e in result if e.signal_date >= since]
        return sorted(result, key=lambda e: e.signal_date, reverse=True)


class StubCoinPriceProvider:
    def __init__(self, prices: dict[tuple[str, date], float]) -> None:
        self._prices = prices

    async def get_close(self, coin: str, asof: date) -> float | None:
        return self._prices.get((coin, asof))


def _make_signal(coin: str = "BTC-USD", action: str = "BUY") -> LiveSignal:
    return LiveSignal(
        coin=coin,
        action=action,
        size_factor=0.5,
        confidence=0.75,
        pred_vol=0.4,
    )


def _make_entry(
    coin: str = "BTC-USD",
    signal_date: date = date(2026, 1, 10),
    action: str = "BUY",
    realized_fwd_return: float | None = None,
) -> PaperLogEntry:
    return PaperLogEntry(
        id=uuid.uuid4(),
        coin=coin,
        signal_date=signal_date,
        action=action,
        size_factor=0.5,
        confidence=0.75,
        pred_vol=0.4,
        realized_fwd_return=realized_fwd_return,
        written_at=datetime.now(UTC),
    )


# ── log_signals ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_signals_writes_correct_count() -> None:
    """log_signals schreibt genau so viele Einträge wie Signale."""
    repo = StubPaperLogRepo()
    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider({}),
    )
    signals = [_make_signal("BTC-USD"), _make_signal("ETH-USD"), _make_signal("SOL-USD")]
    today = date(2026, 1, 10)

    count = await writer.log_signals(signals, today)

    assert count == 3
    assert len(repo.entries) == 3


@pytest.mark.asyncio
async def test_log_signals_sets_correct_date() -> None:
    """Einträge bekommen das korrekte signal_date."""
    repo = StubPaperLogRepo()
    writer = PaperTradingLogWriter(repo=repo, price_provider=StubCoinPriceProvider({}))
    today = date(2026, 6, 26)

    await writer.log_signals([_make_signal()], today)

    assert repo.entries[0].signal_date == today


@pytest.mark.asyncio
async def test_log_signals_each_entry_has_unique_id() -> None:
    """Append-only: jeder Eintrag bekommt eine einzigartige UUID."""
    repo = StubPaperLogRepo()
    writer = PaperTradingLogWriter(repo=repo, price_provider=StubCoinPriceProvider({}))
    signals = [_make_signal() for _ in range(3)]

    await writer.log_signals(signals, date(2026, 1, 10))

    ids = [e.id for e in repo.entries]
    assert len(set(ids)) == 3


@pytest.mark.asyncio
async def test_log_signals_realized_return_is_none() -> None:
    """Neue Signale haben realized_fwd_return = None."""
    repo = StubPaperLogRepo()
    writer = PaperTradingLogWriter(repo=repo, price_provider=StubCoinPriceProvider({}))

    await writer.log_signals([_make_signal()], date(2026, 1, 10))

    assert repo.entries[0].realized_fwd_return is None


# ── fill_outcomes Look-Ahead Guard ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fill_outcomes_look_ahead_guard_not_due() -> None:
    """Eintrag von heute (horizon=1) ist morgen erst fällig → kein Nachtrag."""
    today = date(2026, 1, 10)
    entry = _make_entry(signal_date=today)
    prices = {("BTC-USD", today): 100.0, ("BTC-USD", today + timedelta(days=1)): 105.0}
    repo = StubPaperLogRepo([entry])
    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider(prices),
    )

    filled = await writer.fill_outcomes(asof=today)

    assert filled == 0
    assert entry.id not in repo.backfilled


@pytest.mark.asyncio
async def test_fill_outcomes_look_ahead_guard_now_due() -> None:
    """Eintrag von gestern (horizon=1) ist heute fällig → wird nachgetragen."""
    today = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    entry = _make_entry(signal_date=yesterday)
    prices = {("BTC-USD", yesterday): 100.0, ("BTC-USD", today): 103.0}
    repo = StubPaperLogRepo([entry])
    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider(prices),
    )

    filled = await writer.fill_outcomes(asof=today)

    assert filled == 1
    assert entry.id in repo.backfilled
    assert abs(repo.backfilled[entry.id] - 0.03) < 1e-9


@pytest.mark.asyncio
async def test_fill_outcomes_skips_missing_price() -> None:
    """Kein Nachtrag wenn Preis fehlt."""
    today = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    entry = _make_entry(signal_date=yesterday)
    prices: dict[tuple[str, date], float] = {}  # kein Preis
    repo = StubPaperLogRepo([entry])
    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider(prices),
    )

    filled = await writer.fill_outcomes(asof=today)

    assert filled == 0


@pytest.mark.asyncio
async def test_fill_outcomes_skips_already_filled() -> None:
    """Bereits gefüllte Einträge werden nicht nochmals nachgetragen."""
    today = date(2026, 1, 11)
    yesterday = date(2026, 1, 10)
    entry = _make_entry(signal_date=yesterday, realized_fwd_return=0.05)
    prices = {("BTC-USD", yesterday): 100.0, ("BTC-USD", today): 105.0}
    repo = StubPaperLogRepo()
    # list_pending_outcomes returns only None entries — already filled entry not pending
    repo.entries = [entry]

    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider(prices),
    )

    filled = await writer.fill_outcomes(asof=today)

    assert filled == 0  # already filled → not in pending list


@pytest.mark.asyncio
async def test_fill_outcomes_multiple_entries_mixed() -> None:
    """Mix aus fälligen und nicht-fälligen Einträgen: nur fällige werden nachgetragen."""
    today = date(2026, 1, 12)
    yesterday = date(2026, 1, 11)
    two_days_ago = date(2026, 1, 10)

    entry_due = _make_entry(coin="BTC-USD", signal_date=two_days_ago)
    entry_due2 = _make_entry(coin="ETH-USD", signal_date=yesterday)
    entry_not_due = _make_entry(coin="SOL-USD", signal_date=today)  # due tomorrow

    prices = {
        ("BTC-USD", two_days_ago): 100.0,
        ("BTC-USD", two_days_ago + timedelta(days=1)): 102.0,
        ("ETH-USD", yesterday): 50.0,
        ("ETH-USD", today): 51.0,
    }
    repo = StubPaperLogRepo([entry_due, entry_due2, entry_not_due])
    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider(prices),
    )

    filled = await writer.fill_outcomes(asof=today)

    assert filled == 2
    assert entry_due.id in repo.backfilled
    assert entry_due2.id in repo.backfilled
    assert entry_not_due.id not in repo.backfilled


@pytest.mark.asyncio
async def test_fill_outcomes_custom_horizon() -> None:
    """fill_outcomes respektiert custom horizon (z.B. 5 Tage)."""
    signal_date = date(2026, 1, 1)
    asof = signal_date + timedelta(days=4)  # nur 4 Tage → nicht fällig
    entry = _make_entry(signal_date=signal_date)
    prices = {("BTC-USD", signal_date): 100.0, ("BTC-USD", signal_date + timedelta(days=5)): 110.0}
    repo = StubPaperLogRepo([entry])
    writer = PaperTradingLogWriter(
        repo=repo,
        price_provider=StubCoinPriceProvider(prices),
        horizon=5,
    )

    filled = await writer.fill_outcomes(asof=asof)

    assert filled == 0  # 4 < 5 days → not due
