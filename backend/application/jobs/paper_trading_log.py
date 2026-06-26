"""PaperTradingLogWriter: Append-only log of live signals + realized outcomes (V4-6b).

Täglich:
  1. log_signals(): Schreibt heutige Signale in paper_trading_log.
  2. fill_outcomes(): Trägt realisierte Returns für fällige Einträge nach.

Append-only: niemals UPDATE/DELETE auf Signalzeilen — nur INSERT und backfill_return.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

_logger = logging.getLogger(__name__)

_DEFAULT_HORIZON = 1


@dataclass
class PaperLogEntry:
    id: uuid.UUID
    coin: str
    signal_date: date
    action: str
    size_factor: float
    confidence: float
    pred_vol: float | None
    realized_fwd_return: float | None
    written_at: datetime


@dataclass
class LiveSignal:
    coin: str
    action: str
    size_factor: float
    confidence: float
    pred_vol: float | None


class PaperLogRepository(Protocol):
    async def insert(self, entry: PaperLogEntry) -> None: ...

    async def list_pending_outcomes(self, asof: date) -> list[PaperLogEntry]: ...

    async def backfill_return(self, entry_id: uuid.UUID, realized: float) -> None: ...

    async def list_all(
        self, coin: str | None = None, since: date | None = None
    ) -> list[PaperLogEntry]: ...


class PriceProvider(Protocol):
    async def get_close(self, coin: str, asof: date) -> float | None: ...


class PaperTradingLogWriter:
    """Schreibt Live-Signale und trägt realisierte Outcomes nach."""

    def __init__(
        self,
        repo: PaperLogRepository,
        price_provider: PriceProvider,
        horizon: int = _DEFAULT_HORIZON,
    ) -> None:
        self._repo = repo
        self._prices = price_provider
        self._horizon = horizon

    async def log_signals(self, signals: list[LiveSignal], signal_date: date) -> int:
        """Schreibt neue Signale. Gibt Anzahl geschriebener Einträge zurück."""
        now = datetime.now(tz=UTC)
        written = 0
        for sig in signals:
            entry = PaperLogEntry(
                id=uuid.uuid4(),
                coin=sig.coin,
                signal_date=signal_date,
                action=sig.action,
                size_factor=sig.size_factor,
                confidence=sig.confidence,
                pred_vol=sig.pred_vol,
                realized_fwd_return=None,
                written_at=now,
            )
            await self._repo.insert(entry)
            written += 1
        _logger.info("PaperLog: %d Signale für %s geschrieben", written, signal_date)
        return written

    async def fill_outcomes(self, asof: date) -> int:
        """Trägt realisierte Returns nach. Look-Ahead-Guard: nur wenn Datum fällig."""
        pending = await self._repo.list_pending_outcomes(asof)
        filled = 0
        for entry in pending:
            outcome_date = entry.signal_date + timedelta(days=self._horizon)
            if outcome_date > asof:
                continue

            price_at_signal = await self._prices.get_close(entry.coin, entry.signal_date)
            price_at_outcome = await self._prices.get_close(entry.coin, outcome_date)

            if price_at_signal is None or price_at_outcome is None or price_at_signal <= 0:
                continue

            realized = price_at_outcome / price_at_signal - 1.0
            await self._repo.backfill_return(entry.id, realized)
            filled += 1

        _logger.info("PaperLog: %d Outcomes nachgetragen für asof=%s", filled, asof)
        return filled
