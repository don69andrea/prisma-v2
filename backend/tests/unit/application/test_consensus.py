"""Unit tests for 2-of-3 consensus voting — RED phase (test-first).

Tests cover the full truth table (all 8 binary input combinations) plus
weighted voting and graceful handling of unknown signal columns.
"""
from __future__ import annotations

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Full 2-of-3 truth table
# ---------------------------------------------------------------------------

# (ma_signal, macd_signal, rsi_signal) -> expected_consensus
TRUTH_TABLE = [
    (0, 0, 0, 0),  # none → no signal
    (1, 0, 0, 0),  # only MA → not enough
    (0, 1, 0, 0),  # only MACD → not enough
    (0, 0, 1, 0),  # only RSI → not enough
    (1, 1, 0, 1),  # MA + MACD → 2 of 3 → BUY
    (1, 0, 1, 1),  # MA + RSI → 2 of 3 → BUY
    (0, 1, 1, 1),  # MACD + RSI → 2 of 3 → BUY
    (1, 1, 1, 1),  # all → BUY
]


@pytest.fixture()
def truth_table_df() -> pd.DataFrame:
    """DataFrame with all 8 binary combinations of the 3 signal columns."""
    rows = [
        {"ma_signal": ma, "macd_signal": macd, "rsi_signal": rsi}
        for ma, macd, rsi, _ in TRUTH_TABLE
    ]
    return pd.DataFrame(rows)


def test_consensus_full_truth_table(truth_table_df: pd.DataFrame) -> None:
    """All 8 binary combinations produce the correct 2-of-3 consensus output."""
    from backend.application.signals.consensus import consensus_vote

    result = consensus_vote(truth_table_df)
    expected = pd.Series([exp for *_, exp in TRUTH_TABLE], dtype=int)

    pd.testing.assert_series_equal(
        result.reset_index(drop=True),
        expected,
        check_names=False,
    )


def test_consensus_returns_series(truth_table_df: pd.DataFrame) -> None:
    """consensus_vote() must return a pd.Series aligned to the input index."""
    from backend.application.signals.consensus import consensus_vote

    result = consensus_vote(truth_table_df)
    assert isinstance(result, pd.Series)
    assert result.index.equals(truth_table_df.index)


def test_consensus_series_dtype_is_int(truth_table_df: pd.DataFrame) -> None:
    """Returned series must have integer dtype (0 or 1 values)."""
    from backend.application.signals.consensus import consensus_vote

    result = consensus_vote(truth_table_df)
    assert result.dtype in (int, "int64", "int32")


# ---------------------------------------------------------------------------
# Weighted voting
# ---------------------------------------------------------------------------


def test_consensus_weighted_mode() -> None:
    """With custom weights, weighted sum >= threshold → 1 else 0."""
    from backend.application.signals.consensus import consensus_vote

    # MA has weight 2, MACD weight 1, RSI weight 1 → total weight = 4
    # threshold = 0.5 → need weighted_sum >= 0.5
    # Row with only MA active: weighted_sum = 2/4 = 0.5 → BUY (>= threshold)
    # Row with only RSI active: weighted_sum = 1/4 = 0.25 → NO (< threshold)
    df = pd.DataFrame(
        {
            "ma_signal": [1, 0, 1],
            "macd_signal": [0, 0, 1],
            "rsi_signal": [0, 1, 0],
        }
    )
    cfg = {
        "ma_signal": 2.0,
        "macd_signal": 1.0,
        "rsi_signal": 1.0,
        "threshold": 0.5,
    }
    result = consensus_vote(df, cfg)
    expected = pd.Series([1, 0, 1], dtype=int)
    pd.testing.assert_series_equal(result.reset_index(drop=True), expected, check_names=False)


def test_consensus_custom_threshold() -> None:
    """A higher threshold (e.g. 0.8) requires more signals to be active."""
    from backend.application.signals.consensus import consensus_vote

    # Equal weights, threshold 0.8 → need at least ceil(0.8 * 3) = 3/3 signals
    df = pd.DataFrame(
        {
            "ma_signal": [1, 1, 1],
            "macd_signal": [1, 1, 0],
            "rsi_signal": [1, 0, 0],
        }
    )
    cfg = {
        "ma_signal": 1.0,
        "macd_signal": 1.0,
        "rsi_signal": 1.0,
        "threshold": 0.8,
    }
    result = consensus_vote(df, cfg)
    expected = pd.Series([1, 0, 0], dtype=int)
    pd.testing.assert_series_equal(result.reset_index(drop=True), expected, check_names=False)


# ---------------------------------------------------------------------------
# Graceful handling of unknown signal columns
# ---------------------------------------------------------------------------


def test_consensus_ignores_unknown_columns() -> None:
    """Columns not in cfg weights are ignored gracefully."""
    from backend.application.signals.consensus import consensus_vote

    # cfg only references ma_signal and macd_signal; rsi_signal is extra (ignored)
    df = pd.DataFrame(
        {
            "ma_signal": [1, 0],
            "macd_signal": [1, 0],
            "rsi_signal": [0, 1],  # not in cfg → ignored
            "unknown_col": [1, 1],  # not in cfg → ignored
        }
    )
    cfg = {
        "ma_signal": 1.0,
        "macd_signal": 1.0,
        "threshold": 0.5,
    }
    result = consensus_vote(df, cfg)
    # Row 0: ma=1, macd=1 → sum/total = 2/2 = 1.0 >= 0.5 → 1
    # Row 1: ma=0, macd=0 → sum/total = 0/2 = 0.0 < 0.5 → 0
    expected = pd.Series([1, 0], dtype=int)
    pd.testing.assert_series_equal(result.reset_index(drop=True), expected, check_names=False)


def test_consensus_no_matching_columns_returns_zeros() -> None:
    """If no cfg columns exist in df, returns all zeros gracefully."""
    from backend.application.signals.consensus import consensus_vote

    df = pd.DataFrame({"some_other_col": [1, 1, 1]})
    cfg = {"ma_signal": 1.0, "macd_signal": 1.0, "threshold": 0.5}
    result = consensus_vote(df, cfg)
    assert (result == 0).all(), "Expected all zeros when no cfg columns match"


# ---------------------------------------------------------------------------
# Default cfg (no cfg argument) matches 2-of-3 majority vote
# ---------------------------------------------------------------------------


def test_consensus_default_cfg_is_2_of_3(truth_table_df: pd.DataFrame) -> None:
    """Default cfg (no argument) must produce 2-of-3 majority result."""
    from backend.application.signals.consensus import consensus_vote

    result = consensus_vote(truth_table_df)
    expected = pd.Series([exp for *_, exp in TRUTH_TABLE], dtype=int)
    pd.testing.assert_series_equal(
        result.reset_index(drop=True),
        expected,
        check_names=False,
    )
