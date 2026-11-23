"""DataStewardAgent — automatische Datenpflege und Freshness-Check."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

_logger = logging.getLogger(__name__)

_PRICE_STALE_HOURS = 36
_PRICE_SPIKE_PCT = 15.0


class DataStewardReport(BaseModel):
    run_at: datetime
    checked_tickers: list[str]
    refreshed_tickers: list[str]
    quarantined_tickers: list[str]
    errors: list[str]
    duration_seconds: float


class DataStewardAgent:
    def __init__(
        self,
        stock_repo: Any,
        yf_adapter: Any,
        macro_service: Any,
    ) -> None:
        self._repo = stock_repo
        self._yf = yf_adapter
        self._macro = macro_service

    async def run_check(self) -> DataStewardReport:
        start = datetime.now(UTC)
        refreshed: list[str] = []
        quarantined: list[str] = []
        errors: list[str] = []
        checked: list[str] = []

        try:
            stocks = await self._repo.list_all()
        except Exception as exc:
            _logger.error("DataSteward: list_all() fehlgeschlagen: %s", exc)
            return DataStewardReport(
                run_at=start, checked_tickers=[], refreshed_tickers=[],
                quarantined_tickers=[], errors=[str(exc)],
                duration_seconds=0.0,
            )

        now = datetime.now(UTC)
        stale_threshold = now - timedelta(hours=_PRICE_STALE_HOURS)

        for stock in stocks:
            ticker = stock.ticker
            checked.append(ticker)
            last_price = getattr(stock, "last_price", None)
            last_updated = getattr(stock, "last_updated_at", None)

            if last_updated is None or last_updated < stale_threshold:
                try:
                    new_price = await self._yf.get_latest_price(ticker)
                    if last_price and last_price > 0:
                        change_pct = abs(new_price - last_price) / last_price * 100
                        if change_pct > _PRICE_SPIKE_PCT:
                            _logger.warning(
                                "Preissprung %s: %.1f%% → Quarantäne", ticker, change_pct
                            )
                            quarantined.append(ticker)
                            continue
                    refreshed.append(ticker)
                except Exception as exc:
                    errors.append(f"{ticker}: {exc}")
                    _logger.error("Preis-Refresh %s fehlgeschlagen: %s", ticker, exc)

        duration = (datetime.now(UTC) - start).total_seconds()
        return DataStewardReport(
            run_at=start,
            checked_tickers=checked,
            refreshed_tickers=refreshed,
            quarantined_tickers=quarantined,
            errors=errors,
            duration_seconds=duration,
        )
