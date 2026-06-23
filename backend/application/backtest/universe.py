"""Point-in-Time Universe Membership for the crypto portfolio backtest.

Design:
- ALWAYS_IN: BTC-USD and ETH-USD are always eligible (no volume threshold).
- Other coins: eligible from the first day their trailing-30-day average
  dollar volume (close × volume) ≥ threshold ($100M default).
- Prevents membership look-ahead: eligible_coins(as_of) only returns coins
  that had their first eligibility date ≤ as_of.

Usage:
    from backend.application.backtest.universe import UniverseMembership

    um = UniverseMembership(price_data)          # price_data: dict[str, pd.DataFrame]
    coins = um.eligible_coins(date(2021, 6, 1))  # frozenset[str]
    first_dates = um.first_eligible_dates        # dict[str, date]
"""

from __future__ import annotations

from datetime import date

import pandas as pd

__all__ = ["UniverseMembership", "ALWAYS_IN"]

ALWAYS_IN: frozenset[str] = frozenset({"BTC-USD", "ETH-USD"})

_DEFAULT_THRESHOLD: float = 100_000_000.0  # $100M
_ROLLING_WINDOW: int = 30


class UniverseMembership:
    """PIT universe membership based on trailing-30d average dollar volume.

    Args:
        price_data: Mapping of coin symbol → DataFrame with 'close' and 'volume'
                    columns and a DatetimeIndex.
        threshold:  Minimum trailing-30d average dollar volume (close × volume)
                    for a coin to become eligible. Default: $100M.
    """

    def __init__(
        self,
        price_data: dict[str, pd.DataFrame],
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        self._first_eligible: dict[str, date] = _compute_eligibility(price_data, threshold)

    @property
    def first_eligible_dates(self) -> dict[str, date]:
        """Read-only copy of first-eligible-date mapping."""
        return dict(self._first_eligible)

    def eligible(self, coin: str, as_of: date) -> bool:
        """Return True if *coin* is in the universe on *as_of*."""
        first = self._first_eligible.get(coin)
        return first is not None and first <= as_of

    def eligible_coins(self, as_of: date) -> frozenset[str]:
        """Return all coins eligible on *as_of*."""
        return frozenset(coin for coin, first in self._first_eligible.items() if first <= as_of)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_eligibility(
    price_data: dict[str, pd.DataFrame],
    threshold: float,
) -> dict[str, date]:
    """Compute first-eligible-date for each coin."""
    result: dict[str, date] = {}
    for symbol, df in price_data.items():
        if df.empty:
            continue

        if symbol in ALWAYS_IN:
            first_idx = df.index.min()
            result[symbol] = _as_date(first_idx)
            continue

        if "close" not in df.columns or "volume" not in df.columns:
            continue

        dollar_vol: pd.Series = df["close"] * df["volume"]
        rolling_avg: pd.Series = dollar_vol.rolling(
            _ROLLING_WINDOW, min_periods=_ROLLING_WINDOW
        ).mean()
        eligible_mask: pd.Series = rolling_avg >= threshold
        eligible_indices = df.index[eligible_mask]

        if len(eligible_indices) > 0:
            result[symbol] = _as_date(eligible_indices[0])

    return result


def _as_date(idx: object) -> date:
    if hasattr(idx, "date"):
        return idx.date()  # type: ignore[return-value]
    return idx  # type: ignore[return-value]
