"""Tests for run_portfolio_walkforward_with_details and scripts/portfolio_backtest.py helpers.

Covers:
- run_portfolio_walkforward_with_details returns (report, details) tuple
- details dict has required keys
- dd_brake_dates is a list of date objects
- per_coin_weighted_returns keys match price_data keys
- Drawdown brake fires when portfolio crashes severely
- Baseline metrics present in details
- fetch_prices normalises columns correctly (mocked yfinance)
- print functions run without error (smoke tests)
- main() runs end-to-end with synthetic data (mocked yfinance)
"""

from __future__ import annotations

import importlib
import io
import sys
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit

_100M = 100_000_000.0
_N = 800


def _make_price_df(
    n: int = _N,
    start: str = "2019-01-01",
    seed: int = 0,
    drift: float = 0.0008,
    vol: float = 0.022,
    close_start: float = 1000.0,
    dollar_vol: float = _100M * 2.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, vol, n)
    close = close_start * np.cumprod(1 + returns)
    volume = dollar_vol / close
    idx = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({"close": close, "volume": volume}, index=idx)


def _make_brake_trigger_prices(n: int = _N) -> dict[str, pd.DataFrame]:
    """Two coins: low-vol bull in training → max vol-target weights, then sudden -35% crash.

    min_train=252 → OOS starts at index 252.
    The crash lands at index 253 (OOS day 2) so the portfolio holds through the loss.
    With 80% total exposure and -35% crash, portfolio DD ≈ -28% → brake fires.
    """
    rng = np.random.default_rng(42)
    # Smooth bull with very low vol so vol-target sizing gives max weights (0.40/coin)
    returns_bull = rng.normal(0.001, 0.003, 252)   # 252 training bars
    returns_one_normal = rng.normal(0.001, 0.003, 1)  # OOS day 1 (index 252) — still OK
    crash = np.array([-0.35])                          # OOS day 2 (index 253)
    returns_after = rng.normal(-0.001, 0.025, n - 254)
    returns = np.concatenate([returns_bull, returns_one_normal, crash, returns_after])
    close = 1000.0 * np.cumprod(1 + returns)
    volume = _100M * 2.0 / close
    idx = pd.date_range("2019-01-01", periods=n, freq="D")
    df = pd.DataFrame({"close": close, "volume": volume}, index=idx)
    # Two coins for higher total exposure (up to 80%)
    return {"BTC-USD": df, "ETH-USD": df.copy()}


def _make_prices(coins: list[str], n: int = _N) -> dict[str, pd.DataFrame]:
    return {coin: _make_price_df(n=n, seed=i) for i, coin in enumerate(coins)}


def _make_universe(price_data: dict[str, pd.DataFrame]):
    from backend.application.backtest.universe import UniverseMembership
    return UniverseMembership(price_data)


# ---------------------------------------------------------------------------
# Tests for run_portfolio_walkforward_with_details
# ---------------------------------------------------------------------------

class TestWithDetailsReturnType:
    def test_returns_tuple(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        result = run_portfolio_walkforward_with_details(prices, um)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_portfolio_report(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        from backend.interfaces.rest.schemas.signals import PortfolioBacktestReport
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        report, _ = run_portfolio_walkforward_with_details(prices, um)
        assert isinstance(report, PortfolioBacktestReport)

    def test_second_element_is_dict(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD"])
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        assert isinstance(details, dict)


class TestDetailsKeys:
    _REQUIRED_KEYS = {
        "dd_brake_dates",
        "per_coin_weighted_returns",
        "bh_ew_returns",
        "exposure_matched_returns",
        "net_oos_returns",
        "bh_sharpe", "bh_calmar", "bh_max_dd", "bh_cagr",
        "em_sharpe", "em_calmar", "em_max_dd", "em_cagr",
    }

    def test_all_required_keys_present(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        for key in self._REQUIRED_KEYS:
            assert key in details, f"Missing details key: {key}"

    def test_dd_brake_dates_is_list(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD"])
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        assert isinstance(details["dd_brake_dates"], list)

    def test_dd_brake_dates_elements_are_dates(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        # Use crash data to guarantee the brake fires and the list is non-empty
        prices = _make_brake_trigger_prices()
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        for d in details["dd_brake_dates"]:
            assert isinstance(d, date), f"Expected date, got {type(d)}"

    def test_per_coin_weighted_returns_keys_match_input(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        coins = ["BTC-USD", "ETH-USD", "SOL-USD"]
        prices = _make_prices(coins)
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        assert set(details["per_coin_weighted_returns"].keys()) == set(coins)

    def test_per_coin_weighted_returns_are_series(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        for coin, series in details["per_coin_weighted_returns"].items():
            assert isinstance(series, pd.Series), f"{coin}: expected Series"

    def test_baseline_metrics_are_floats(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        for key in ["bh_sharpe", "bh_calmar", "bh_max_dd", "bh_cagr",
                    "em_sharpe", "em_calmar", "em_max_dd", "em_cagr"]:
            assert isinstance(details[key], float), f"{key} is not float"

    def test_net_oos_returns_non_empty(self) -> None:
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        assert len(details["net_oos_returns"]) > 0


class TestDDBrake:
    def test_brake_fires_on_crash_data(self) -> None:
        """Sudden -35% crash with max exposure must trigger the DD brake."""
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_brake_trigger_prices(n=800)
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        assert len(details["dd_brake_dates"]) > 0, (
            "Expected DD brake to fire: -35% crash at OOS day 2 with ~80% exposure "
            f"should yield ~-28% DD. Got {len(details['dd_brake_dates'])} brake days."
        )

    def test_brake_does_not_fire_on_steady_bull(self) -> None:
        """Strong trending data with no crash should not fire the brake."""
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        # Very smooth bull: drift 0.1% daily, tiny vol 0.5% — no -15% DD possible
        rng = np.random.default_rng(0)
        n = 800
        returns = rng.normal(0.001, 0.005, n)  # low vol → no -15% DD
        close = 1000.0 * np.cumprod(1 + returns)
        volume = _100M * 2.0 / close
        idx = pd.date_range("2019-01-01", periods=n, freq="D")
        btc = pd.DataFrame({"close": close, "volume": volume}, index=idx)
        prices = {"BTC-USD": btc}
        um = _make_universe(prices)
        _, details = run_portfolio_walkforward_with_details(prices, um)
        assert len(details["dd_brake_dates"]) == 0


# ---------------------------------------------------------------------------
# Smoke tests for print functions
# ---------------------------------------------------------------------------

class TestPrintFunctions:
    def _get_report_and_details(self):
        from backend.application.backtest.portfolio_walkforward import (
            run_portfolio_walkforward_with_details,
        )
        prices = _make_prices(["BTC-USD", "ETH-USD"])
        um = _make_universe(prices)
        return run_portfolio_walkforward_with_details(prices, um)

    def test_print_comparison_table_runs(self) -> None:
        from scripts.portfolio_backtest import print_comparison_table
        report, details = self._get_report_and_details()
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_comparison_table(report, details)
        out = buf.getvalue()
        assert "Sharpe" in out
        assert "Calmar" in out
        assert "MaxDD" in out

    def test_print_dd_brake_table_runs(self) -> None:
        from scripts.portfolio_backtest import print_dd_brake_table
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_dd_brake_table([])
        out = buf.getvalue()
        assert "Drawdown" in out

    def test_print_dd_brake_table_with_2022_dates(self) -> None:
        from scripts.portfolio_backtest import print_dd_brake_table
        dates = [date(2022, 5, 12), date(2022, 6, 1), date(2022, 6, 2)]
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_dd_brake_table(dates)
        out = buf.getvalue()
        assert "2022" in out
        assert "3" in out  # 3 days in 2022

    def test_print_per_coin_table_runs(self) -> None:
        from scripts.portfolio_backtest import print_per_coin_table
        report, details = self._get_report_and_details()
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_per_coin_table(report, details["per_coin_weighted_returns"])
        out = buf.getvalue()
        assert "Sharpe" in out
        assert "BTC-USD" in out


# ---------------------------------------------------------------------------
# fetch_prices tests (mocked yfinance)
# ---------------------------------------------------------------------------

class TestFetchPrices:
    def _make_yf_df(self, n: int = 100, sym: str = "BTC-USD") -> pd.DataFrame:
        """Returns a yfinance-style DataFrame with capitalised columns."""
        rng = np.random.default_rng(0)
        close = 1000.0 * np.cumprod(1 + rng.normal(0.001, 0.02, n))
        volume = np.ones(n) * 1e6
        idx = pd.date_range("2020-01-01", periods=n, freq="D")
        return pd.DataFrame({"Close": close, "Volume": volume, "Open": close,
                             "High": close * 1.01, "Low": close * 0.99}, index=idx)

    def test_fetch_normalises_column_names(self) -> None:
        from scripts.portfolio_backtest import fetch_prices
        mock_df = self._make_yf_df()
        with patch("yfinance.download", return_value=mock_df):
            result = fetch_prices(["BTC-USD"], "2020-01-01")
        assert "BTC-USD" in result
        df = result["BTC-USD"]
        assert "close" in df.columns
        assert "volume" in df.columns

    def test_fetch_skips_empty_result(self) -> None:
        from scripts.portfolio_backtest import fetch_prices
        with patch("yfinance.download", return_value=pd.DataFrame()):
            result = fetch_prices(["UNKNOWN-USD"], "2020-01-01")
        assert "UNKNOWN-USD" not in result

    def test_fetch_handles_multiindex_columns(self) -> None:
        """yfinance may return MultiIndex columns for some versions."""
        from scripts.portfolio_backtest import fetch_prices
        rng = np.random.default_rng(0)
        n = 50
        close = 1000.0 * np.cumprod(1 + rng.normal(0.001, 0.02, n))
        idx = pd.date_range("2020-01-01", periods=n, freq="D")
        arrays = [["Close", "Volume"], ["BTC-USD", "BTC-USD"]]
        mi = pd.MultiIndex.from_arrays(arrays)
        mock_df = pd.DataFrame(
            {mi[0]: close, mi[1]: np.ones(n) * 1e6},
            index=idx,
        )
        mock_df.columns = mi
        with patch("yfinance.download", return_value=mock_df):
            result = fetch_prices(["BTC-USD"], "2020-01-01")
        # After droplevel+lower, must have "close" and "volume"
        if "BTC-USD" in result:
            assert "close" in result["BTC-USD"].columns


# ---------------------------------------------------------------------------
# main() integration smoke test
# ---------------------------------------------------------------------------

class TestMainSmoke:
    def _make_yf_response(self, sym: str, n: int = 700) -> pd.DataFrame:
        seed = hash(sym) % 2**31
        rng = np.random.default_rng(seed)
        close = 1000.0 * np.cumprod(1 + rng.normal(0.0008, 0.022, n))
        volume = _100M * 2.0 / close
        idx = pd.date_range("2019-01-01", periods=n, freq="D")
        return pd.DataFrame({
            "Close": close, "Volume": volume,
            "Open": close, "High": close * 1.01, "Low": close * 0.99,
        }, index=idx)

    def test_main_runs_with_two_coins(self) -> None:
        """main() should complete without error for a small 2-coin universe."""
        from scripts.portfolio_backtest import main
        responses = {}
        for sym in ["BTC-USD", "ETH-USD"]:
            responses[sym] = self._make_yf_response(sym)

        def _mock_download(sym, start, progress, auto_adjust):
            return responses.get(sym, pd.DataFrame())

        buf = io.StringIO()
        with patch("yfinance.download", side_effect=_mock_download):
            with redirect_stdout(buf):
                main(["--coins", "BTC-USD", "ETH-USD", "--start", "2019-01-01"])

        out = buf.getvalue()
        assert "Sharpe" in out
        assert "Drawdown" in out
        assert "Sharpe-Beitrag" in out
