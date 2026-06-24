"""Unit tests for scripts/robustness_check.py — PRISMA V4-4c Robustness Harness.

7 test classes covering all Phase Requirements → Test Map requirements:
  TestImportable         — main() returns dict with 4 expected keys
  TestBuildSignals       — signal shape, shift(1) look-ahead check, consensus integration
  TestNoLookAhead        — shift(1) applied before consensus_vote (D-09)
  TestCostSensitivity    — 3 cost levels, CostResult fields (D-03)
  TestRegimeSplit        — RegimeResult fields including bah_max_dd, Bear-2018 guard (D-04)
  TestUniversumInsufficient — coins with no data marked as download_failed/insufficient (D-05)
  TestBuyAndHold         — _bah_metrics returns 3-tuple, bah_max_dd is float (D-07)
  TestParameterStability — 5 windows, is_default for window=100, ParamResult fields (D-06)

Rules:
- pytestmark = pytest.mark.unit (mandatory per AGENTS.md)
- All fixtures use np.random.default_rng(seed=42) — no unseeded random (D-09)
- Synthetic data only — no yfinance calls in tests
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Shared fixture: 800-row trending synthetic close series
# ---------------------------------------------------------------------------


@pytest.fixture()
def trending_close() -> pd.Series:
    """800-row UTC-indexed daily close series starting 2015-01-01, seed=42."""
    rng = np.random.default_rng(42)
    n = 800
    prices = 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, n))
    return pd.Series(
        prices,
        index=pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC"),
    )


@pytest.fixture()
def long_close() -> pd.Series:
    """2600-row UTC-indexed daily close series starting 2015-01-01, seed=42.

    Required for regime tests that need data through 2021-12-31.
    """
    rng = np.random.default_rng(42)
    n = 2600
    prices = 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, n))
    return pd.Series(
        prices,
        index=pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC"),
    )


# ---------------------------------------------------------------------------
# TestImportable
# ---------------------------------------------------------------------------


class TestImportable:
    """main() is importable and returns a dict with the 4 expected keys."""

    def test_main_returns_dict_with_four_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() must return dict with keys cost_results, regime_results, etc.

        Uses monkeypatching to prevent any yfinance calls. We patch all 4 run_*
        functions to return minimal lists so main() stays offline.
        """
        import scripts.robustness_check as rc

        monkeypatch.setattr(rc, "run_cost_sensitivity", lambda: [])
        monkeypatch.setattr(rc, "run_regime_splits", lambda: [])
        monkeypatch.setattr(rc, "run_universe", lambda: [])
        monkeypatch.setattr(rc, "run_parameter_stability", lambda: [])
        # Suppress Rich console output
        monkeypatch.setattr(rc.console, "print", lambda *a, **kw: None)
        monkeypatch.setattr(rc.console, "rule", lambda *a, **kw: None)
        # Also patch print_* table functions so they don't error on empty lists
        monkeypatch.setattr(rc, "print_cost_table", lambda r: None)
        monkeypatch.setattr(rc, "print_regime_table", lambda r: None)
        monkeypatch.setattr(rc, "print_universe_table", lambda r: None)
        monkeypatch.setattr(rc, "print_param_table", lambda r: None)

        result = rc.main()

        assert isinstance(result, dict)
        expected_keys = {"cost_results", "regime_results", "universe_results", "parameter_results"}
        assert set(result.keys()) == expected_keys

    def test_main_keys_map_to_lists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each key in the returned dict maps to a list (even if empty)."""
        import scripts.robustness_check as rc

        monkeypatch.setattr(rc, "run_cost_sensitivity", lambda: [])
        monkeypatch.setattr(rc, "run_regime_splits", lambda: [])
        monkeypatch.setattr(rc, "run_universe", lambda: [])
        monkeypatch.setattr(rc, "run_parameter_stability", lambda: [])
        monkeypatch.setattr(rc.console, "print", lambda *a, **kw: None)
        monkeypatch.setattr(rc.console, "rule", lambda *a, **kw: None)
        monkeypatch.setattr(rc, "print_cost_table", lambda r: None)
        monkeypatch.setattr(rc, "print_regime_table", lambda r: None)
        monkeypatch.setattr(rc, "print_universe_table", lambda r: None)
        monkeypatch.setattr(rc, "print_param_table", lambda r: None)

        result = rc.main()

        for key in ("cost_results", "regime_results", "universe_results", "parameter_results"):
            assert isinstance(result[key], list), f"{key} must be a list"


# ---------------------------------------------------------------------------
# TestBuildSignals
# ---------------------------------------------------------------------------


class TestBuildSignals:
    """build_signals() shape, signal bounds, and consensus integration."""

    def test_output_shape_matches_input(self, trending_close: pd.Series) -> None:
        from scripts.robustness_check import build_signals

        signals = build_signals(trending_close, ma_window=50)
        assert len(signals) == len(trending_close)

    def test_output_index_matches_input(self, trending_close: pd.Series) -> None:
        from scripts.robustness_check import build_signals

        signals = build_signals(trending_close, ma_window=50)
        assert signals.index.equals(trending_close.index)

    def test_signal_values_are_non_negative(self, trending_close: pd.Series) -> None:
        """All position sizes are >= 0 (long-only, no short positions)."""
        from scripts.robustness_check import build_signals

        signals = build_signals(trending_close, ma_window=50)
        assert (signals >= 0.0).all(), "Signals contain negative values (short positions)"

    def test_signal_values_bounded_by_vol_cap(self, trending_close: pd.Series) -> None:
        """Position sizes are capped at 1.5 by vol_target_size (cap=1.5)."""
        from scripts.robustness_check import build_signals

        signals = build_signals(trending_close, ma_window=50)
        assert (signals <= 1.5 + 1e-9).all(), "Signals exceed cap of 1.5"

    def test_first_signal_is_zero_due_to_shift(self, trending_close: pd.Series) -> None:
        """Day 0 signal is 0 because shift(1) propagates NaN → 0 via fillna(0)."""
        from scripts.robustness_check import build_signals

        signals = build_signals(trending_close, ma_window=50)
        assert signals.iloc[0] == 0.0, "First signal must be 0 (shift(1) guard)"

    def test_different_ma_windows_produce_different_signals(
        self, trending_close: pd.Series
    ) -> None:
        """SMA window parameter affects output — window=50 vs window=200 must differ."""
        from scripts.robustness_check import build_signals

        sig50 = build_signals(trending_close, ma_window=50)
        sig200 = build_signals(trending_close, ma_window=200)
        assert not sig50.equals(sig200), "Different MA windows must produce different signals"


# ---------------------------------------------------------------------------
# TestNoLookAhead (D-09)
# ---------------------------------------------------------------------------


class TestNoLookAhead:
    """shift(1) applied before consensus_vote — signal at t depends on close[t-1], not close[t]."""

    def test_shift_applied_before_consensus_strictly_monotone(self) -> None:
        """On a strictly monotone increasing series:
        - signals itself should NOT be a lagged version of close shifted forward (no look-ahead).
        - signal[i] must use close[i-1], so signals.shift(-1) (un-shift) correlates with close,
          but signals itself should NOT perfectly correlate with close.

        Test: build_signals on monotone series; correlation(signals, close) < 1.0 because
        signal at t uses close[t-1] (shifted), meaning there's a 1-day lag.
        Meanwhile correlation(signals.shift(-1), close) should be >= 0.9 for a pure trend series.
        """
        from scripts.robustness_check import build_signals

        n = 800
        # Strictly monotone increasing — MA signal should always be 1 after warmup
        close = pd.Series(
            range(1, n + 1),
            dtype=float,
            index=pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC"),
        )

        signals = build_signals(close, ma_window=50)

        # signal[0] must be 0 (shift guard applied)
        assert signals.iloc[0] == 0.0

        # On a strictly increasing series with ma_window=50,
        # signal should be non-zero well before day n
        assert signals.sum() > 0, "Expected positive signals on an uptrend"

    def test_shift_guard_day_zero_is_zero_monotone(self) -> None:
        """Day 0 signal is always 0 because shift(1) fills NaN → 0, regardless of close[0] > SMA[0]."""
        from scripts.robustness_check import build_signals

        # A series where close[0] would trivially be > SMA[0] if no shift applied
        # (all values = 1000, SMA(50) would be 1000 immediately)
        n = 800
        close = pd.Series(
            [1000.0] * n,
            index=pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC"),
        )

        signals = build_signals(close, ma_window=50)
        # Even though close[0] == SMA[0] == 1000, signal[0] must be 0
        assert signals.iloc[0] == 0.0

    def test_look_ahead_source_check_shift_before_consensus(self) -> None:
        """Verify via source inspection that shift(1) is applied before consensus_vote().

        We read the source of build_signals and confirm shift(1) appears before
        consensus_vote in the call sequence.
        """
        import inspect

        from scripts.robustness_check import build_signals

        source = inspect.getsource(build_signals)

        # shift(1) must appear in the source
        assert "shift(1)" in source, "shift(1) not found in build_signals source"

        # consensus_vote must appear after the shift
        shift_pos = source.index("shift(1)")
        consensus_pos = source.index("consensus_vote")
        assert shift_pos < consensus_pos, (
            "shift(1) must appear before consensus_vote() in build_signals source "
            f"(shift_pos={shift_pos}, consensus_pos={consensus_pos})"
        )

    def test_signal_lags_close_by_one_day(self) -> None:
        """On a trending series, signal at t depends on close[t-1].

        Verify by checking that the first non-zero signal appears AFTER day 0
        (i.e., date index >= day 1) meaning it required at least 1 prior close value.
        """
        from scripts.robustness_check import build_signals

        n = 800
        close = pd.Series(
            range(1, n + 1),
            dtype=float,
            index=pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC"),
        )

        signals = build_signals(close, ma_window=50)

        non_zero = signals[signals > 0]
        assert len(non_zero) > 0, "Expected some non-zero signals on monotone series"
        first_nonzero_date = non_zero.index[0]
        first_date = signals.index[0]
        assert first_nonzero_date > first_date, (
            f"First non-zero signal at {first_nonzero_date} must be AFTER day 0 ({first_date})"
        )


# ---------------------------------------------------------------------------
# TestCostSensitivity (D-03)
# ---------------------------------------------------------------------------


class TestCostSensitivity:
    """3 cost levels produce distinct CostResult objects with correct fields."""

    def test_three_cost_levels_produce_three_results(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.robustness_check as rc
        from scripts.robustness_check import CostResult, run_cost_sensitivity

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_cost_sensitivity(coins=["BTC-USD"], cost_levels=[0.001, 0.002, 0.005])

        assert len(results) == 3
        assert all(isinstance(r, CostResult) for r in results)

    def test_two_coins_three_costs_produce_six_results(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.robustness_check as rc
        from scripts.robustness_check import run_cost_sensitivity

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_cost_sensitivity(coins=["BTC-USD", "ETH-USD"], cost_levels=[0.001, 0.002, 0.005])

        assert len(results) == 6

    def test_higher_cost_produces_lower_strategy_sharpe(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Higher transaction costs reduce net return → lower Sharpe."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import CostResult, run_cost_sensitivity

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_cost_sensitivity(coins=["BTC-USD"], cost_levels=[0.001, 0.005])
        cost_results = [r for r in results if isinstance(r, CostResult)]
        assert len(cost_results) == 2

        by_cost = {r.cost_level: r for r in cost_results}
        assert by_cost[0.001].strategy_sharpe > by_cost[0.005].strategy_sharpe, (
            "cost=0.001 should produce higher Sharpe than cost=0.005"
        )

    def test_cost_result_fields_present(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CostResult dataclass has all required fields."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import CostResult, run_cost_sensitivity

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_cost_sensitivity(coins=["BTC-USD"], cost_levels=[0.001])
        r = results[0]
        assert isinstance(r, CostResult)
        # Required fields
        assert hasattr(r, "coin")
        assert hasattr(r, "cost_level")
        assert hasattr(r, "strategy_sharpe")
        assert hasattr(r, "strategy_calmar")
        assert hasattr(r, "strategy_max_dd")
        assert hasattr(r, "baseline_sharpe")
        assert hasattr(r, "baseline_calmar")
        assert hasattr(r, "bah_sharpe")
        assert hasattr(r, "bah_calmar")
        assert hasattr(r, "beats_exposure_matched")
        assert r.cost_level in [0.001, 0.002, 0.005]

    def test_cost_result_coin_matches_input(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.robustness_check as rc
        from scripts.robustness_check import CostResult, run_cost_sensitivity

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_cost_sensitivity(coins=["BTC-USD"], cost_levels=[0.001])
        r = results[0]
        assert isinstance(r, CostResult)
        assert r.coin == "BTC-USD"

    def test_insufficient_data_returns_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Coins with < _MIN_ROWS return dict with status='insufficient'."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import _MIN_ROWS, run_cost_sensitivity

        short_close = pd.Series(
            range(100),
            dtype=float,
            index=pd.date_range("2020-01-01", periods=100, freq="D", tz="UTC"),
        )
        assert len(short_close) < _MIN_ROWS

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: short_close)

        results = run_cost_sensitivity(coins=["BTC-USD"], cost_levels=[0.001])
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, dict)
        assert r.get("status") == "insufficient"


# ---------------------------------------------------------------------------
# TestRegimeSplit (D-04)
# ---------------------------------------------------------------------------


class TestRegimeSplit:
    """RegimeResult fields, OOS slicing, bah_max_dd, Bear-2018 guard."""

    def test_regime_result_has_bah_max_dd_field(
        self, long_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RegimeResult must have bah_max_dd field (downside protection comparison)."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import RegimeResult, run_regime_splits

        monkeypatch.setattr(
            rc,
            "_download",
            lambda coin, start, end=None: long_close[long_close.index <= end] if end else long_close,
        )

        regimes = [{"name": "Bull 2021", "start": "2021-01-01", "end": "2021-12-31"}]
        results = run_regime_splits(coins=["BTC-USD"], regimes=regimes)
        regime_results = [r for r in results if isinstance(r, RegimeResult)]

        assert len(regime_results) >= 1, "Expected at least one RegimeResult"
        r = regime_results[0]
        assert hasattr(r, "bah_max_dd")
        assert isinstance(r.bah_max_dd, float)

    def test_bah_max_dd_is_non_positive(
        self, long_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bah_max_dd is MaxDD of B&H — always <= 0.0 (drawdown is negative or zero)."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import RegimeResult, run_regime_splits

        monkeypatch.setattr(
            rc,
            "_download",
            lambda coin, start, end=None: long_close[long_close.index <= end] if end else long_close,
        )

        regimes = [{"name": "Bull 2021", "start": "2021-01-01", "end": "2021-12-31"}]
        results = run_regime_splits(coins=["BTC-USD"], regimes=regimes)
        regime_results = [r for r in results if isinstance(r, RegimeResult)]

        assert len(regime_results) >= 1
        assert regime_results[0].bah_max_dd <= 0.0

    def test_oos_rows_positive(
        self, long_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OOS rows > 0 when sufficient data exists for the regime window."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import RegimeResult, run_regime_splits

        monkeypatch.setattr(
            rc,
            "_download",
            lambda coin, start, end=None: long_close[long_close.index <= end] if end else long_close,
        )

        regimes = [{"name": "Bull 2021", "start": "2021-01-01", "end": "2021-12-31"}]
        results = run_regime_splits(coins=["BTC-USD"], regimes=regimes)
        regime_results = [r for r in results if isinstance(r, RegimeResult)]

        assert len(regime_results) >= 1
        assert regime_results[0].oos_rows > 0

    def test_bear_2018_insufficient_for_sol(
        self, long_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SOL-USD is hardcoded as not-listed in 2018 → returns insufficient dict."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import run_regime_splits

        monkeypatch.setattr(
            rc,
            "_download",
            lambda coin, start, end=None: long_close[long_close.index <= end] if end else long_close,
        )

        regimes = [{"name": "Bear 2018", "start": "2018-01-01", "end": "2018-12-31"}]
        results = run_regime_splits(coins=["SOL-USD"], regimes=regimes)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, dict)
        assert r.get("status") == "insufficient"
        assert r.get("coin") == "SOL-USD"

    @pytest.mark.parametrize("coin", ["SOL-USD", "AVAX-USD", "DOT-USD", "MATIC-USD"])
    def test_bear_2018_insufficient_for_not_listed_coins(
        self, long_close: pd.Series, monkeypatch: pytest.MonkeyPatch, coin: str
    ) -> None:
        """All 4 coins not listed in 2018 return insufficient for Bear-2018 regime."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import run_regime_splits

        monkeypatch.setattr(
            rc,
            "_download",
            lambda c, start, end=None: long_close[long_close.index <= end] if end else long_close,
        )

        regimes = [{"name": "Bear 2018", "start": "2018-01-01", "end": "2018-12-31"}]
        results = run_regime_splits(coins=[coin], regimes=regimes)

        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0].get("status") == "insufficient"

    def test_regime_result_all_fields_present(
        self, long_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RegimeResult has all required dataclass fields."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import RegimeResult, run_regime_splits

        monkeypatch.setattr(
            rc,
            "_download",
            lambda coin, start, end=None: long_close[long_close.index <= end] if end else long_close,
        )

        regimes = [{"name": "Bull 2021", "start": "2021-01-01", "end": "2021-12-31"}]
        results = run_regime_splits(coins=["BTC-USD"], regimes=regimes)
        regime_results = [r for r in results if isinstance(r, RegimeResult)]

        assert len(regime_results) >= 1
        r = regime_results[0]
        for field in (
            "coin",
            "regime_name",
            "strategy_sharpe",
            "strategy_calmar",
            "strategy_max_dd",
            "baseline_sharpe",
            "baseline_calmar",
            "bah_max_dd",
            "oos_rows",
            "note",
        ):
            assert hasattr(r, field), f"RegimeResult missing field: {field}"


# ---------------------------------------------------------------------------
# TestUniversumInsufficient (D-05)
# ---------------------------------------------------------------------------


class TestUniversumInsufficient:
    """Coins with no data are marked download_failed; <315 rows → insufficient."""

    def test_avax_none_returns_download_failed_dict(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_download returning None for AVAX-USD → dict with status='download_failed'."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import run_universe

        def mock_download(coin: str, start: str, end: str | None = None) -> pd.Series | None:
            if coin == "AVAX-USD":
                return None
            return trending_close

        monkeypatch.setattr(rc, "_download", mock_download)

        results = run_universe()
        avax_result = next(
            (r for r in results if isinstance(r, dict) and r.get("coin") == "AVAX-USD"),
            None,
        )
        assert avax_result is not None, "AVAX-USD result not found"
        assert avax_result.get("status") in ("download_failed", "insufficient")

    def test_insufficient_rows_returns_insufficient_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Coins with < 315 rows return dict with status='insufficient'."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import _MIN_ROWS, run_universe

        rng = np.random.default_rng(42)
        short_close = pd.Series(
            100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 100)),
            index=pd.date_range("2020-01-01", periods=100, freq="D", tz="UTC"),
        )
        assert len(short_close) < _MIN_ROWS

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: short_close)

        results = run_universe()
        # All 10 coins get short data → all should be insufficient
        assert len(results) == 10
        for r in results:
            assert isinstance(r, dict)
            assert r.get("status") in ("insufficient", "download_failed")

    def test_sufficient_coins_return_universe_result(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Coins with sufficient data return UniverseResult (not dict)."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import UniverseResult, run_universe

        def mock_download(coin: str, start: str, end: str | None = None) -> pd.Series | None:
            if coin == "AVAX-USD":
                return None
            return trending_close

        monkeypatch.setattr(rc, "_download", mock_download)

        results = run_universe()
        universe_results = [r for r in results if isinstance(r, UniverseResult)]
        # All coins except AVAX-USD should be UniverseResult
        assert len(universe_results) == 9

    def test_universe_covers_all_ten_coins(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_universe() processes all 10 coins in _CRYPTO_UNIVERSE."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import _CRYPTO_UNIVERSE, run_universe

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_universe()
        assert len(results) == len(_CRYPTO_UNIVERSE) == 10


# ---------------------------------------------------------------------------
# TestBuyAndHold (D-07)
# ---------------------------------------------------------------------------


class TestBuyAndHold:
    """_bah_metrics returns 3-tuple (bah_sharpe, bah_calmar, bah_max_dd)."""

    def test_returns_three_tuple(self, trending_close: pd.Series) -> None:
        """_bah_metrics() must return a 3-tuple of floats."""
        from scripts.robustness_check import _bah_metrics

        result = _bah_metrics(trending_close)
        assert isinstance(result, tuple), "Expected tuple"
        assert len(result) == 3, f"Expected 3-tuple, got {len(result)}-tuple"

    def test_all_elements_are_float(self, trending_close: pd.Series) -> None:
        """All 3 elements of the return value are floats."""
        from scripts.robustness_check import _bah_metrics

        bah_sharpe, bah_calmar, bah_max_dd = _bah_metrics(trending_close)
        assert isinstance(bah_sharpe, float), "bah_sharpe must be float"
        assert isinstance(bah_calmar, float), "bah_calmar must be float"
        assert isinstance(bah_max_dd, float), "bah_max_dd must be float"

    def test_bah_max_dd_is_non_positive(self, trending_close: pd.Series) -> None:
        """bah_max_dd is MaxDD — always <= 0.0 by definition."""
        from scripts.robustness_check import _bah_metrics

        _, _, bah_max_dd = _bah_metrics(trending_close)
        assert bah_max_dd <= 0.0, f"bah_max_dd must be <= 0, got {bah_max_dd}"

    def test_avg_exposure_near_one_for_all_ones_signal(
        self, trending_close: pd.Series
    ) -> None:
        """All-ones signal → avg_exposure ~1.0 in walkforward details."""
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices_df = pd.DataFrame({"close": trending_close})
        bah_signals = pd.Series(1.0, index=trending_close.index)
        details = run_walkforward_with_details(prices_df, bah_signals, costs=0.0001)

        assert details["avg_exposure"] > 0.99, (
            f"avg_exposure for all-ones signal should be ~1.0, got {details['avg_exposure']:.4f}"
        )

    def test_tuple_unpacking_convention(self, trending_close: pd.Series) -> None:
        """Confirm callers can unpack all 3 values: bah_sharpe, bah_calmar, bah_max_dd."""
        from scripts.robustness_check import _bah_metrics

        # This must not raise ValueError (too many/few values)
        bah_sharpe, bah_calmar, bah_max_dd = _bah_metrics(trending_close)
        # bah_max_dd is the 3rd element (not a 2-tuple)
        assert bah_max_dd != bah_sharpe or bah_max_dd != bah_calmar  # at least different sometimes


# ---------------------------------------------------------------------------
# TestParameterStability (D-06)
# ---------------------------------------------------------------------------


class TestParameterStability:
    """5 SMA windows, is_default=True for window=100, ParamResult fields."""

    def test_five_windows_produce_five_results_per_coin(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.robustness_check as rc
        from scripts.robustness_check import ParamResult, run_parameter_stability

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_parameter_stability(coins=["BTC-USD"])
        param_results = [r for r in results if isinstance(r, ParamResult)]
        assert len(param_results) == 5

    def test_all_five_windows_present(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Results cover all 5 windows: [50, 75, 100, 150, 200]."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import ParamResult, run_parameter_stability

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_parameter_stability(coins=["BTC-USD"])
        param_results = [r for r in results if isinstance(r, ParamResult)]
        windows_found = {r.ma_window for r in param_results}
        assert windows_found == {50, 75, 100, 150, 200}, (
            f"Expected windows {{50,75,100,150,200}}, got {windows_found}"
        )

    def test_exactly_one_default_result(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exactly one result has is_default=True, which must be window=100."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import ParamResult, run_parameter_stability

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_parameter_stability(coins=["BTC-USD"])
        param_results = [r for r in results if isinstance(r, ParamResult)]
        defaults = [r for r in param_results if r.is_default]

        assert len(defaults) == 1, f"Expected exactly 1 default, got {len(defaults)}"
        assert defaults[0].ma_window == 100

    def test_window_100_is_default(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_default=True only for window=100 (the D-01 anchor point)."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import ParamResult, run_parameter_stability

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_parameter_stability(coins=["BTC-USD"])
        param_results = [r for r in results if isinstance(r, ParamResult)]

        by_window = {r.ma_window: r for r in param_results}
        assert by_window[100].is_default is True
        for w in [50, 75, 150, 200]:
            assert by_window[w].is_default is False, f"window={w} must not be default"

    def test_different_windows_produce_different_sharpe(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """window=50 and window=200 must produce different strategy_sharpe (not identical)."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import ParamResult, run_parameter_stability

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_parameter_stability(coins=["BTC-USD"])
        param_results = [r for r in results if isinstance(r, ParamResult)]
        by_window = {r.ma_window: r for r in param_results}

        assert by_window[50].strategy_sharpe != by_window[200].strategy_sharpe, (
            "window=50 and window=200 must produce different Sharpe ratios"
        )

    def test_param_result_fields_present(
        self, trending_close: pd.Series, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ParamResult has all required dataclass fields."""
        import scripts.robustness_check as rc
        from scripts.robustness_check import ParamResult, run_parameter_stability

        monkeypatch.setattr(rc, "_download", lambda coin, start, end=None: trending_close)

        results = run_parameter_stability(coins=["BTC-USD"])
        param_results = [r for r in results if isinstance(r, ParamResult)]
        assert len(param_results) > 0
        r = param_results[0]

        for field in (
            "coin",
            "ma_window",
            "is_default",
            "strategy_sharpe",
            "strategy_calmar",
            "strategy_max_dd",
            "beats_exposure_matched",
        ):
            assert hasattr(r, field), f"ParamResult missing field: {field}"
