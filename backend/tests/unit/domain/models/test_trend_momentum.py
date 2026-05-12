"""Tests für Trend Momentum — EWMA der relativen Returns vs. equal-weighted Universum.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §3
      docs/specs/2026-04-27-quant-models-redesign.md §3.1
"""

import numpy as np
import pandas as pd
import pytest

from backend.domain.models.trend_momentum import TrendMomentumModel

pytestmark = pytest.mark.unit


def _run(prices: pd.DataFrame) -> dict[str, int | None]:
    """Hilfsfunktion: gibt {ticker: rank} zurück."""
    results = TrendMomentumModel().run(prices=prices)
    return {r.ticker: r.rank for r in results}


def _make_prices(returns: pd.DataFrame, start: float = 100.0) -> pd.DataFrame:
    """Wandelt Daily-Returns in Preise (kumuliert) um."""
    return start * (1 + returns).cumprod()


class TestTrendMomentumSpecConstants:
    def test_constants_match_spec(self) -> None:
        model = TrendMomentumModel()
        assert model.HALFLIFE_DAYS == 63
        assert model.MIN_PERIODS == 32


class TestTrendMomentumFormula:
    def test_outperformer_ranks_first(self) -> None:
        """3-Ticker Golden Dataset:
        - A: täglich +0.1% relativ zum Universum-Mean → Rang 1
        - B: konstant am Mean → Mittelfeld
        - C: täglich -0.1% relativ → schlechtester Rang
        """
        n_days = 250
        index = pd.date_range("2024-01-01", periods=n_days, freq="B")
        rng = np.random.default_rng(42)

        # Marktrendite + idiosynkratisches Rauschen pro Ticker
        market = rng.normal(0.0005, 0.01, n_days)
        a_returns = market + 0.001  # +0.1% / Tag relativ über Markt
        b_returns = market.copy()
        c_returns = market - 0.001  # -0.1% / Tag relativ unter Markt

        returns = pd.DataFrame(
            {"A": a_returns, "B": b_returns, "C": c_returns},
            index=index,
        )
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["A"] == 1
        assert ranks["C"] == 3

    def test_identical_prices_yield_equal_rank(self) -> None:
        """Alle Ticker mit identischen Preisreihen → relative Returns = 0 → alle rank=1."""
        n = 100
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(7)
        single_path = (1 + rng.normal(0.0005, 0.01, n)).cumprod() * 100

        prices = pd.DataFrame(
            {"X": single_path, "Y": single_path, "Z": single_path},
            index=index,
        )
        ranks = _run(prices)
        assert ranks["X"] == ranks["Y"] == ranks["Z"] == 1

    def test_recent_outperformance_weighted_higher(self) -> None:
        """EWMA halflife=63: Recent-Spike-Ticker schlägt gleichschlechten Langfrist-Outperformer.

        Setup: 200 Tage Historie, zwei Ticker mit *gleicher* Gesamt-Outperformance:
        - A: konstanter Bias +0.1% täglich über die ganze Historie
        - B: erste 100 Tage neutral, letzte 100 Tage +0.2% täglich
        Beide haben am Ende ähnliche kumulierte Outperformance, aber B's Outperformance
        ist *jünger* → EWMA mit halflife=63 sollte B höher gewichten als A.
        """
        n = 200
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        market = np.zeros(n)  # neutraler Markt zur Kontrolle

        a_returns = market + 0.001
        b_returns = market.copy()
        b_returns[100:] = 0.002  # erst spät outperformt

        returns = pd.DataFrame({"A": a_returns, "B": b_returns}, index=index)
        prices = _make_prices(returns)

        results = {r.ticker: r.score for r in TrendMomentumModel().run(prices=prices)}
        assert results["A"] is not None
        assert results["B"] is not None
        # B's recent outperformance dominates EWMA
        assert results["B"] > results["A"]

    def test_deterministic(self) -> None:
        n = 80
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(11)
        prices = _make_prices(
            pd.DataFrame(
                {
                    "P": rng.normal(0.0005, 0.01, n),
                    "Q": rng.normal(0.0005, 0.012, n),
                    "R": rng.normal(0.0005, 0.008, n),
                },
                index=index,
            )
        )
        assert _run(prices) == _run(prices)


class TestTrendMomentumEdgeCases:
    def test_empty_universe_returns_empty(self) -> None:
        assert TrendMomentumModel().run(prices=pd.DataFrame()) == []

    def test_insufficient_datapoints_yields_no_ranks(self) -> None:
        """< 32 Datenpunkte (min_periods) → EWMA NaN → rank=None für alle."""
        n = 20
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(1)
        prices = _make_prices(
            pd.DataFrame(
                {"A": rng.normal(0.0005, 0.01, n), "B": rng.normal(0.0005, 0.012, n)},
                index=index,
            )
        )

        results = TrendMomentumModel().run(prices=prices)
        assert all(r.rank is None for r in results)
        assert all(r.confidence == "low" for r in results)

    def test_single_ticker_yields_rank_one(self) -> None:
        """1 Ticker → Benchmark = Ticker → rel_returns = 0 → score=0 → rank=1."""
        n = 60
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(0)
        prices = _make_prices(pd.DataFrame({"SOLO": rng.normal(0.0005, 0.01, n)}, index=index))

        results = TrendMomentumModel().run(prices=prices)
        assert len(results) == 1
        assert results[0].ticker == "SOLO"
        assert results[0].rank == 1
