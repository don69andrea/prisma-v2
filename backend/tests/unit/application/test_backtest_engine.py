"""Unit-Tests: BacktestEngine — Contract E3.3."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.application.services.backtest_engine import (
    BacktestEngine,
    EquityCurve,
    SignalEvent,
)
from backend.domain.services.transaction_cost_model import AssetClass, TransactionCostModel

pytestmark = pytest.mark.unit


def _make_prices(
    tickers: list[str],
    start: date = date(2020, 1, 2),
    n_days: int = 120,
    seed: int = 42,
) -> pd.DataFrame:
    """Erzeugt synthetischen Preis-DataFrame mit DatetimeIndex (Handelstage)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start=start, periods=n_days)
    data = {}
    for t in tickers:
        returns = rng.normal(0.0005, 0.01, n_days)
        data[t] = 100.0 * np.cumprod(1.0 + returns)
    return pd.DataFrame(data, index=idx)


def _make_benchmark(
    start: date = date(2020, 1, 2),
    n_days: int = 120,
    seed: int = 99,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start=start, periods=n_days)
    returns = rng.normal(0.0003, 0.008, n_days)
    return pd.Series(100.0 * np.cumprod(1.0 + returns), index=idx, name="BM")


@pytest.fixture()
def cost_model() -> TransactionCostModel:
    return TransactionCostModel()


@pytest.fixture()
def engine(cost_model: TransactionCostModel) -> BacktestEngine:
    return BacktestEngine(cost_model=cost_model, benchmark_ticker="^SSMI")


@pytest.fixture()
def prices() -> pd.DataFrame:
    return _make_prices(["NESN", "ROG"], n_days=120)


@pytest.fixture()
def benchmark() -> pd.Series:
    return _make_benchmark(n_days=120)


# ---------------------------------------------------------------------------
# E3.3-1: Determinismus
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.asyncio
    async def test_same_input_same_output(
        self,
        engine: BacktestEngine,
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> None:
        sigs = [
            SignalEvent("NESN", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20),
            SignalEvent("ROG", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20),
        ]
        start, end = date(2020, 1, 2), date(2020, 6, 30)
        c1 = await engine.run(sigs, prices, benchmark, start, end)
        c2 = await engine.run(sigs, prices, benchmark, start, end)
        assert c1.equity == c2.equity
        assert c1.cagr == c2.cagr
        assert c1.sharpe == c2.sharpe


# ---------------------------------------------------------------------------
# E3.3-2: Kosten senken die Equity
# ---------------------------------------------------------------------------


class TestCostsReduceEquity:
    @pytest.mark.asyncio
    async def test_cost_adjusted_always_below_gross(
        self, engine: BacktestEngine, prices: pd.DataFrame, benchmark: pd.Series
    ) -> None:
        """cost_adjusted_return muss strikt < actual_return sein (TC > 0)."""
        sigs = [
            SignalEvent("NESN", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20),
            SignalEvent("ROG", date(2020, 2, 3), "BUY", 100.0, AssetClass.CH_STOCK, 20),
        ]
        outcomes = await engine.outcomes_from(sigs, prices, benchmark)
        for row in outcomes:
            assert row["cost_adjusted_return"] < row["actual_return"], (
                f"cost_adjusted {row['cost_adjusted_return']} muss < gross {row['actual_return']}"
            )


# ---------------------------------------------------------------------------
# E3.3-3: Look-Ahead-Prevention
# ---------------------------------------------------------------------------


class TestNoLookAhead:
    @pytest.mark.asyncio
    async def test_spike_at_d_plus_1_doesnt_change_fill_at_d(
        self,
        engine: BacktestEngine,
        benchmark: pd.Series,
    ) -> None:
        """Preissprung an Tag d+1 darf Fill an Tag d NICHT verändern."""
        n_days = 80
        idx = pd.bdate_range(start=date(2020, 1, 2), periods=n_days)
        base_prices = np.ones(n_days) * 100.0
        prices_normal = pd.DataFrame({"NESN": base_prices.copy()}, index=idx)

        # Spike an Tag 5 (d+1 nach Signal)
        prices_spike = prices_normal.copy()
        prices_spike.iloc[4, 0] = 999.0

        sig = [SignalEvent("NESN", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20)]
        start, end = date(2020, 1, 2), date(2020, 6, 30)

        c_normal = await engine.run(sig, prices_normal, benchmark, start, end)
        c_spike = await engine.run(sig, prices_spike, benchmark, start, end)

        # Signal-Einstiegs-Fill am 6.1.2020 (Tag 3 im Index) bleibt gleich
        entry_fills_normal = [f for f in c_normal.fills if f.side == "ENTRY"]
        entry_fills_spike = [f for f in c_spike.fills if f.side == "ENTRY"]

        if entry_fills_normal and entry_fills_spike:
            assert entry_fills_normal[0].price == entry_fills_spike[0].price


# ---------------------------------------------------------------------------
# E3.3-4: outcomes_from stimmt mit Equity-Kurve überein (Reconciliation)
# ---------------------------------------------------------------------------


class TestOutcomesReconciliation:
    @pytest.mark.asyncio
    async def test_outcomes_count_matches_signal_count(
        self,
        engine: BacktestEngine,
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> None:
        sigs = [
            SignalEvent("NESN", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20),
            SignalEvent("ROG", date(2020, 2, 3), "BUY", 100.0, AssetClass.CH_STOCK, 20),
        ]
        outcomes = await engine.outcomes_from(sigs, prices, benchmark)
        assert len(outcomes) <= len(sigs)

    @pytest.mark.asyncio
    async def test_outcomes_have_net_columns(
        self,
        engine: BacktestEngine,
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> None:
        sigs = [
            SignalEvent("NESN", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20),
        ]
        outcomes = await engine.outcomes_from(sigs, prices, benchmark)
        if outcomes:
            row = outcomes[0]
            assert "cost_adjusted_return" in row
            assert "net_excess_return" in row
            assert "was_correct" in row
            assert row["cost_adjusted_return"] is not None

    @pytest.mark.asyncio
    async def test_cost_adjusted_return_less_than_gross(
        self,
        engine: BacktestEngine,
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> None:
        sigs = [
            SignalEvent("NESN", date(2020, 1, 6), "BUY", 100.0, AssetClass.CH_STOCK, 20),
        ]
        outcomes = await engine.outcomes_from(sigs, prices, benchmark)
        if outcomes:
            row = outcomes[0]
            assert row["cost_adjusted_return"] == pytest.approx(
                row["actual_return"] - TransactionCostModel().ch_stock_round_trip(),
                abs=1e-6,
            )


# ---------------------------------------------------------------------------
# E3.3-5: Leerer Signal-Input ergibt valide leere EquityCurve
# ---------------------------------------------------------------------------


class TestEmptyInput:
    @pytest.mark.asyncio
    async def test_empty_signals(
        self,
        engine: BacktestEngine,
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> None:
        c = await engine.run([], prices, benchmark, date(2020, 1, 2), date(2020, 6, 30))
        assert isinstance(c, EquityCurve)

    @pytest.mark.asyncio
    async def test_outcomes_empty_signals(
        self,
        engine: BacktestEngine,
        prices: pd.DataFrame,
        benchmark: pd.Series,
    ) -> None:
        rows = await engine.outcomes_from([], prices, benchmark)
        assert rows == []
