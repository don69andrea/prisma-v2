"""Tests für StubMarketDataProvider — deterministischer Random-Walk pro Ticker.

Spec: docs/specs/2026-05-09-ranking-service-multi-model.md §"Stub-Adapter"
"""

import numpy as np
import pandas as pd
import pytest

from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider

pytestmark = pytest.mark.unit


class TestStubMarketDataShape:
    @pytest.mark.asyncio
    async def test_returns_dataframe_with_expected_shape(self) -> None:
        """Spec: Shape 504 × N, Index tz-aware UTC, Business-Day-Frequenz."""
        stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
        df = await stub.get_prices(["AAPL", "MSFT", "GOOGL"])
        assert df.shape == (504, 3)
        assert df.index.tz is not None
        assert str(df.index.tz) == "UTC"
        assert list(df.columns) == ["AAPL", "MSFT", "GOOGL"]

    @pytest.mark.asyncio
    async def test_empty_tickers_returns_empty_df(self) -> None:
        stub = StubMarketDataProvider()
        df = await stub.get_prices([])
        assert df.empty


class TestStubMarketDataDeterminism:
    @pytest.mark.asyncio
    async def test_deterministic_across_runs(self) -> None:
        """Spec: zlib.crc32-Seed muss prozess-stabil sein.

        Zwei Stub-Instanzen mit gleichem end_date → identische Reihen pro Ticker.
        """
        end = pd.Timestamp("2026-05-09", tz="UTC")
        df1 = await StubMarketDataProvider(end_date=end).get_prices(["AAPL"])
        df2 = await StubMarketDataProvider(end_date=end).get_prices(["AAPL"])
        np.testing.assert_array_equal(df1["AAPL"].to_numpy(), df2["AAPL"].to_numpy())

    @pytest.mark.asyncio
    async def test_end_date_is_injectable(self) -> None:
        """Fixed end_date → fixed Index (sonst sind Tests zeitabhängig)."""
        end = pd.Timestamp("2026-01-15", tz="UTC")
        stub = StubMarketDataProvider(end_date=end)
        df = await stub.get_prices(["AAPL"])
        assert df.index[-1] <= end


class TestStubMarketDataEdgeCases:
    @pytest.mark.asyncio
    async def test_unknown_ticker_still_gets_random_walk(self) -> None:
        """Stub kennt jeden Ticker via Hash-Seed — kein Lookup-Table nötig."""
        stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
        df = await stub.get_prices(["NEVERHEARDOFIT"])
        assert df.shape == (504, 1)
        assert "NEVERHEARDOFIT" in df.columns

    @pytest.mark.asyncio
    async def test_returns_finite_positive_prices(self) -> None:
        """Cumulative-Product aus normal-distributed Returns mit drift>0,
        sollte praktisch nie negativ oder NaN werden über 504 Tage.
        """
        stub = StubMarketDataProvider(end_date=pd.Timestamp("2026-05-09", tz="UTC"))
        df = await stub.get_prices(["AAPL", "MSFT"])
        assert df.notna().all().all()
        assert (df > 0).all().all()
        assert np.isfinite(df.to_numpy()).all()
