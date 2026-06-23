"""Unit tests for backend.application.backtest.universe (Phase 06-01).

PIT (Point-In-Time) Universe Membership:
- BTC/ETH: ALWAYS_IN (no volume threshold)
- Other coins: eligible from first day trailing-30d avg dollar-vol ≥ $100M
- coin not seen in price_data → never eligible
- eligible_coins(as_of) returns frozenset[str]
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit

_100M = 100_000_000.0


def _make_df(n: int, close: float, volume: float, start: str = "2019-01-01") -> pd.DataFrame:
    """Minimal OHLCV DataFrame (only close+volume required for universe calc)."""
    idx = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({"close": close, "volume": volume}, index=idx)


class TestUniverseAlwaysIn:
    def test_btc_eligible_from_first_day(self) -> None:
        from backend.application.backtest.universe import UniverseMembership, ALWAYS_IN
        assert "BTC-USD" in ALWAYS_IN
        assert "ETH-USD" in ALWAYS_IN

    def test_btc_eligible_even_with_zero_volume(self) -> None:
        """BTC/ETH always eligible regardless of dollar volume."""
        from backend.application.backtest.universe import UniverseMembership
        prices = {"BTC-USD": _make_df(400, close=1.0, volume=0.0)}
        um = UniverseMembership(prices)
        d = date(2019, 2, 1)
        assert um.eligible("BTC-USD", d)
        assert "BTC-USD" in um.eligible_coins(d)

    def test_eth_eligible_even_with_low_volume(self) -> None:
        from backend.application.backtest.universe import UniverseMembership
        prices = {"ETH-USD": _make_df(400, close=1.0, volume=1.0)}
        um = UniverseMembership(prices)
        assert um.eligible("ETH-USD", date(2019, 6, 1))


class TestUniversePITMembership:
    def test_coin_ineligible_before_threshold_met(self) -> None:
        """A coin should NOT be eligible before its 30d avg dollar-vol crosses $100M."""
        from backend.application.backtest.universe import UniverseMembership
        # volume=0 → dollar_vol=0, never meets $100M
        prices = {"SOL-USD": _make_df(400, close=100.0, volume=0.0)}
        um = UniverseMembership(prices)
        assert not um.eligible("SOL-USD", date(2019, 12, 31))

    def test_coin_eligible_after_threshold_met(self) -> None:
        """Coin becomes eligible from the first day trailing-30d avg ≥ $100M."""
        from backend.application.backtest.universe import UniverseMembership
        n = 200
        idx = pd.date_range("2019-01-01", periods=n, freq="D")
        # First 100 days: low volume (below threshold)
        # Days 101+: high volume so rolling-30 avg crosses $100M
        close = pd.Series(100.0, index=idx)
        volume = pd.Series(0.0, index=idx)
        # Set high volume from day 101 onwards → 30d avg ≥ $100M after day 130
        volume.iloc[100:] = _100M * 1.1 / 100.0  # close=100, vol = 1.1M → dollar_vol=110M
        df = pd.DataFrame({"close": close, "volume": volume}, index=idx)
        um = UniverseMembership({"XRP-USD": df})
        # Should not be eligible early
        assert not um.eligible("XRP-USD", date(2019, 4, 5))
        # Should be eligible after rolling avg crossed threshold (around day 130)
        assert um.eligible("XRP-USD", date(2019, 6, 30))

    def test_eligible_coins_returns_frozenset(self) -> None:
        from backend.application.backtest.universe import UniverseMembership
        prices = {
            "BTC-USD": _make_df(400, close=50000.0, volume=1e6),
            "ETH-USD": _make_df(400, close=3000.0, volume=1e6),
        }
        um = UniverseMembership(prices)
        result = um.eligible_coins(date(2019, 6, 1))
        assert isinstance(result, frozenset)
        assert "BTC-USD" in result
        assert "ETH-USD" in result

    def test_unknown_coin_not_eligible(self) -> None:
        """A coin absent from price_data is never eligible."""
        from backend.application.backtest.universe import UniverseMembership
        prices = {"BTC-USD": _make_df(400, close=50000.0, volume=1e6)}
        um = UniverseMembership(prices)
        assert not um.eligible("UNKNOWN-USD", date(2022, 1, 1))
        assert "UNKNOWN-USD" not in um.eligible_coins(date(2022, 1, 1))

    def test_first_eligible_date_is_exposed(self) -> None:
        """first_eligible_date dict maps eligible coins to their first date."""
        from backend.application.backtest.universe import UniverseMembership
        prices = {"BTC-USD": _make_df(400, close=50000.0, volume=1e6)}
        um = UniverseMembership(prices)
        dates = um.first_eligible_dates
        assert "BTC-USD" in dates
        assert isinstance(dates["BTC-USD"], date)


class TestUniverseCustomThreshold:
    def test_custom_threshold_respected(self) -> None:
        """A lower threshold makes coins eligible sooner."""
        from backend.application.backtest.universe import UniverseMembership
        # dollar_vol = 100 * 500k = $50M — below default $100M, above $10M custom
        prices = {"ADA-USD": _make_df(400, close=100.0, volume=500_000.0)}
        um_default = UniverseMembership(prices)
        um_low = UniverseMembership(prices, threshold=10_000_000.0)
        # With default threshold: ADA should NOT be eligible
        assert not um_default.eligible("ADA-USD", date(2019, 6, 1))
        # With $10M threshold: ADA should be eligible
        assert um_low.eligible("ADA-USD", date(2019, 6, 1))


class TestUniverseMultiCoin:
    def test_multiple_coins_varying_eligibility(self) -> None:
        """eligible_coins(date) returns only coins that are eligible at that date."""
        from backend.application.backtest.universe import UniverseMembership
        n = 400
        idx = pd.date_range("2019-01-01", periods=n, freq="D")

        # BTC: always in
        btc = pd.DataFrame({"close": 50000.0, "volume": 1000.0}, index=idx)
        # SOL: high volume → eligible immediately
        sol = pd.DataFrame({"close": 100.0, "volume": _100M / 100.0 * 1.1}, index=idx)
        # DOGE: zero volume → never eligible
        doge = pd.DataFrame({"close": 0.1, "volume": 0.0}, index=idx)

        um = UniverseMembership({"BTC-USD": btc, "SOL-USD": sol, "DOGE-USD": doge})
        result = um.eligible_coins(date(2019, 3, 1))
        assert "BTC-USD" in result
        assert "SOL-USD" in result
        assert "DOGE-USD" not in result
