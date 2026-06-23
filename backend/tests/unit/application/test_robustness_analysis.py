"""Unit tests for scripts/robustness_analysis.py (V4-4c).

Tests cover:
- run_robustness_analysis() runs without error on synthetic data
- Results have correct structure (RobustnessRow fields)
- beats_exposure_matched is a bool per row
- At least one cost level / coin combination beats the baseline on trending data
"""

from __future__ import annotations

import os
import sys

import pytest

pytestmark = pytest.mark.unit

# Make scripts/ importable
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class TestRobustnessAnalysis:
    def test_runs_and_returns_rows(self) -> None:
        """run_robustness_analysis returns non-empty list of RobustnessRow."""
        from scripts.robustness_analysis import run_robustness_analysis

        rows = run_robustness_analysis(
            coins=["BTC-USD", "ETH-USD"],
            ma_windows=[100],
            cost_levels=[0.001],
        )
        assert len(rows) == 2

    def test_row_fields_present(self) -> None:
        """Each row has all required fields."""
        from scripts.robustness_analysis import run_robustness_analysis

        rows = run_robustness_analysis(
            coins=["BTC-USD"],
            ma_windows=[100],
            cost_levels=[0.001],
        )
        row = rows[0]
        assert row.coin == "BTC-USD"
        assert row.ma_window == 100
        assert row.costs_pct == pytest.approx(0.1)
        assert isinstance(row.sharpe, float)
        assert isinstance(row.calmar, float)
        assert isinstance(row.max_dd, float)
        assert isinstance(row.beats, bool)

    def test_max_dd_is_non_positive(self) -> None:
        """Maximum drawdown must be ≤ 0 (loss, not gain)."""
        from scripts.robustness_analysis import run_robustness_analysis

        rows = run_robustness_analysis(
            coins=["BTC-USD", "ETH-USD"],
            ma_windows=[100],
            cost_levels=[0.001],
        )
        for row in rows:
            assert row.max_dd <= 0.0, f"{row.coin} max_dd={row.max_dd} should be ≤ 0"

    def test_trending_data_beats_baseline_at_low_cost(self) -> None:
        """On synthetic trending data, at least 1 coin beats baseline at 0.1% cost."""
        from scripts.robustness_analysis import run_robustness_analysis

        rows = run_robustness_analysis(
            coins=list(
                __import__(
                    "scripts.robustness_analysis", fromlist=["_COIN_SPECS"]
                )._COIN_SPECS.keys()
            ),
            ma_windows=[100],
            cost_levels=[0.001],
        )
        beats_count = sum(r.beats for r in rows)
        assert beats_count >= 1, "Expected at least 1 coin to beat baseline on trending data"

    def test_higher_costs_reduce_beats(self) -> None:
        """Increasing cost levels should not INCREASE beats count."""
        from scripts.robustness_analysis import run_robustness_analysis

        rows_low = run_robustness_analysis(
            coins=["BTC-USD", "ETH-USD", "SOL-USD"],
            ma_windows=[100],
            cost_levels=[0.001],
        )
        rows_high = run_robustness_analysis(
            coins=["BTC-USD", "ETH-USD", "SOL-USD"],
            ma_windows=[100],
            cost_levels=[0.005],
        )
        beats_low = sum(r.beats for r in rows_low)
        beats_high = sum(r.beats for r in rows_high)
        assert beats_high <= beats_low, (
            f"Higher costs should not increase beats: {beats_high} > {beats_low}"
        )

    def test_all_ten_coins_run(self) -> None:
        """All 10 coins in the universe can be analyzed."""
        from scripts.robustness_analysis import _COIN_SPECS, run_robustness_analysis

        rows = run_robustness_analysis(
            coins=list(_COIN_SPECS.keys()),
            ma_windows=[100],
            cost_levels=[0.001],
        )
        assert len(rows) == 10
        coins_in_results = {r.coin for r in rows}
        assert coins_in_results == set(_COIN_SPECS.keys())
