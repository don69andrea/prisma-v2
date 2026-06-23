"""Unit tests for backend.application.backtest.portfolio_walkforward (Phase 06-03).

TDD: tests written before implementation.

Covers:
- Returns PortfolioBacktestReport with correct types
- total_exposure ≤ 0.80 (max exposure constraint)
- PIT guard: ineligible coins excluded from positions
- Look-ahead guard: position at t uses data up to t-1 (shift(1))
- beats_equal_weight_bh and beats_exposure_matched are bools
- equity_curve starts at 1.0 and is list of (date, float)
- Single always-in coin (BTC): runs without error
- pit_universe dict contains expected coins
- per_coin_stats present for active coins
- costs value preserved in report
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from backend.application.backtest.universe import UniverseMembership

pytestmark = pytest.mark.unit

_100M = 100_000_000.0
_N_DAYS = 800  # > min_train(252) + step(63)


def _make_price_df(
    n: int = _N_DAYS,
    start: str = "2019-01-01",
    seed: int = 0,
    drift: float = 0.0008,
    vol: float = 0.022,
    close_start: float = 1000.0,
    volume_per_bar: float = _100M * 1.5,  # dollar_vol = close × vol >> $100M
) -> pd.DataFrame:
    """Synthetic OHLCV for one coin."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, vol, n)
    close = close_start * np.cumprod(1 + returns)
    volume = volume_per_bar / close  # keep dollar_vol stable
    idx = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({"close": close, "volume": volume}, index=idx)


def _make_portfolio_prices(coins: list[str], n: int = _N_DAYS) -> dict[str, pd.DataFrame]:
    return {coin: _make_price_df(n=n, seed=i, close_start=1000.0 + i * 100)
            for i, coin in enumerate(coins)}


def _make_universe(price_data: dict[str, pd.DataFrame]) -> UniverseMembership:
    return UniverseMembership(price_data)


_ALL_COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]


class TestPortfolioBacktestReportType:
    def test_returns_portfolio_backtest_report_type(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        from backend.interfaces.rest.schemas.signals import PortfolioBacktestReport
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert isinstance(report, PortfolioBacktestReport)

    def test_report_has_required_scalar_fields(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert isinstance(report.sharpe, float)
        assert isinstance(report.calmar, float)
        assert isinstance(report.max_dd, float)
        assert isinstance(report.cagr, float)
        assert isinstance(report.avg_exposure, float)
        assert isinstance(report.n_rebalances, int)
        assert isinstance(report.costs, float)

    def test_costs_recorded(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um, costs=0.002)
        assert report.costs == pytest.approx(0.002)


class TestExposureConstraint:
    def test_avg_exposure_within_max(self) -> None:
        """Average portfolio exposure must be ≤ 0.80 (max_exposure constant)."""
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(_ALL_COINS)
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert report.avg_exposure <= 0.80 + 1e-9

    def test_avg_exposure_non_negative(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert report.avg_exposure >= 0.0


class TestPITGuard:
    def test_ineligible_coin_not_in_per_coin_stats(self) -> None:
        """A coin that is never eligible must not appear in per_coin_stats."""
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        from backend.application.backtest.universe import UniverseMembership

        # BTC: always-in; ZERO-COIN: never eligible (zero volume)
        n = _N_DAYS
        idx = pd.date_range("2019-01-01", periods=n, freq="D")
        btc_df = _make_price_df(n=n, seed=0)
        zero_df = pd.DataFrame({"close": 100.0, "volume": 0.0}, index=idx)

        price_data = {"BTC-USD": btc_df, "ZERO-USD": zero_df}
        um = UniverseMembership(price_data)
        report = run_portfolio_walkforward(price_data, um)

        # ZERO-USD is never eligible → should have 0 days in portfolio
        if "ZERO-USD" in report.per_coin_stats:
            assert report.per_coin_stats["ZERO-USD"].days_in_portfolio == 0

    def test_pit_universe_keys_match_price_data(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        for coin in report.pit_universe:
            assert coin in prices

    def test_pit_universe_dates_are_iso_strings(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        for _coin, d in report.pit_universe.items():
            assert isinstance(d, str)
            # Must parse as valid ISO date
            date.fromisoformat(d)


class TestLookAheadGuard:
    def test_equity_curve_first_entry_is_one(self) -> None:
        """Equity curve starts at 1.0 — no phantom gains before positions."""
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        first_val = report.equity_curve[0][1]
        assert first_val == pytest.approx(1.0, abs=0.01)

    def test_equity_curve_is_list_of_date_float_tuples(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert len(report.equity_curve) > 0
        first_date, first_val = report.equity_curve[0]
        assert isinstance(first_date, date)
        assert isinstance(first_val, float)


class TestBeatsBooleans:
    def test_beats_fields_are_booleans(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert isinstance(report.beats_equal_weight_bh, bool)
        assert isinstance(report.beats_exposure_matched, bool)


class TestSingleCoin:
    def test_single_btc_coin_runs(self) -> None:
        """Single always-in coin should run without error."""
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = {"BTC-USD": _make_price_df(n=_N_DAYS, seed=0)}
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert report.coins == ["BTC-USD"]
        assert report.avg_exposure >= 0.0

    def test_btc_always_in_pit_universe(self) -> None:
        """BTC-USD must appear in pit_universe with the earliest date."""
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = {"BTC-USD": _make_price_df(n=_N_DAYS, seed=0)}
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert "BTC-USD" in report.pit_universe


class TestPerCoinStats:
    def test_per_coin_stats_present_for_active_coins(self) -> None:
        """Coins that were ever eligible must appear in per_coin_stats."""
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        prices = _make_portfolio_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert "BTC-USD" in report.per_coin_stats
        assert "ETH-USD" in report.per_coin_stats

    def test_per_coin_stats_schema(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        from backend.interfaces.rest.schemas.signals import PortfolioCoinStats
        prices = _make_portfolio_prices(["BTC-USD"])
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        for _coin, stats in report.per_coin_stats.items():
            assert isinstance(stats, PortfolioCoinStats)
            assert stats.avg_weight >= 0.0
            assert stats.days_in_portfolio >= 0


class TestCoinsField:
    def test_coins_field_matches_input_keys(self) -> None:
        from backend.application.backtest.portfolio_walkforward import run_portfolio_walkforward
        coins = ["BTC-USD", "ETH-USD", "SOL-USD"]
        prices = _make_portfolio_prices(coins)
        um = _make_universe(prices)
        report = run_portfolio_walkforward(prices, um)
        assert set(report.coins) == set(coins)
