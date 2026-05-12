"""Tests für Alpha — Multi-Horizon Sharpe-gewichtete Outperformance.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §2
      docs/specs/2026-04-21-prisma-capstone-design.md §6.3
"""

import numpy as np
import pandas as pd
import pytest

from backend.domain.models.alpha import AlphaModel

pytestmark = pytest.mark.unit


def _run(prices: pd.DataFrame) -> dict[str, int | None]:
    """Hilfsfunktion: gibt {ticker: rank} zurück."""
    results = AlphaModel().run(prices=prices)
    return {r.ticker: r.rank for r in results}


def _make_prices(returns: pd.DataFrame, start: float = 100.0) -> pd.DataFrame:
    """Wandelt Daily-Returns in kumulierte Preise."""
    return start * (1 + returns).cumprod()


class TestAlphaSpecConstants:
    def test_constants_match_spec(self) -> None:
        model = AlphaModel()
        assert model.HORIZONS == (5, 63, 126, 252, 504)
        assert model.WEIGHTS == (0.10, 0.15, 0.25, 0.30, 0.20)
        assert sum(model.WEIGHTS) == pytest.approx(1.0)
        assert model.SHARPE_WEIGHT == 0.05
        assert model.MIN_PERIODS == 32


class TestAlphaFormula:
    def test_multi_horizon_outperformer_ranks_first(self) -> None:
        """3-Ticker Golden Dataset über alle 5 Horizonte verfügbar:
        - A: täglich +0.1% relativ → konsistent stärkster
        - B: konstant am Mean
        - C: täglich -0.1% relativ → konsistent schwächster
        → A rank 1, C rank 3.
        """
        n = 600  # ≥ 504 → alle Horizonte verfügbar
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        market = np.zeros(n)
        a_returns = market + 0.001
        b_returns = market.copy()
        c_returns = market - 0.001

        returns = pd.DataFrame({"A": a_returns, "B": b_returns, "C": c_returns}, index=index)
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["A"] == 1
        assert ranks["C"] == 3

    def test_lower_volatility_wins_at_similar_outperformance(self) -> None:
        """Sharpe-Influence: Zwei Ticker mit ähnlicher mittlerer Outperformance,
        aber stark unterschiedlicher Daily-Volatilität.
        - A: deterministisch +0.001 / Tag (niedrige Vola, hohe Sharpe)
        - B: gleicher Mittelwert, aber alternierender ±0.02 Rausch (hohe Vola, tiefe Sharpe)
        - C: 0 (Marktanker im equal-weighted Universum)
        Spec §2 Test-Approach: 'Ticker mit gleicher Outperformance aber höherer
        Volatilität → tieferer Score'. A muss höher gerankt werden als B.
        """
        n = 600
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        a_returns = np.full(n, 0.001)
        noise = np.array([0.02 if i % 2 == 0 else -0.02 for i in range(n)])
        b_returns = 0.001 + noise
        c_returns = np.zeros(n)

        returns = pd.DataFrame({"A": a_returns, "B": b_returns, "C": c_returns}, index=index)
        prices = _make_prices(returns)

        results = {r.ticker: r.score for r in AlphaModel().run(prices=prices)}
        assert results["A"] is not None
        assert results["B"] is not None
        assert results["A"] > results["B"]

    def test_identical_prices_yield_equal_rank(self) -> None:
        """Alle Ticker mit identischen Preisreihen → outperformance = 0,
        sharpe = 0 (Spec §2: std=0 → Sharpe=0) → alle Score gleich → alle rank 1.
        """
        n = 250
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(7)
        single_path = (1 + rng.normal(0.0005, 0.01, n)).cumprod() * 100
        prices = pd.DataFrame(
            {"X": single_path, "Y": single_path, "Z": single_path},
            index=index,
        )
        ranks = _run(prices)
        assert ranks["X"] == ranks["Y"] == ranks["Z"] == 1

    def test_deterministic(self) -> None:
        n = 250
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(13)
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


class TestAlphaEdgeCases:
    def test_empty_universe_returns_empty(self) -> None:
        assert AlphaModel().run(prices=pd.DataFrame()) == []

    def test_single_ticker_yields_rank_one(self) -> None:
        """1 Ticker → benchmark = ticker → outperformance = 0 → rank=1."""
        n = 100
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(0)
        prices = _make_prices(pd.DataFrame({"SOLO": rng.normal(0.0005, 0.01, n)}, index=index))

        results = AlphaModel().run(prices=prices)
        assert len(results) == 1
        assert results[0].ticker == "SOLO"
        assert results[0].rank == 1

    def test_insufficient_datapoints_yields_low_confidence(self) -> None:
        """< 32 Handelstage (MIN_PERIODS) → rank=None, confidence='low'."""
        n = 20
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(1)
        prices = _make_prices(
            pd.DataFrame(
                {"A": rng.normal(0.0005, 0.01, n), "B": rng.normal(0.0005, 0.012, n)},
                index=index,
            )
        )

        results = AlphaModel().run(prices=prices)
        assert all(r.rank is None for r in results)
        assert all(r.confidence == "low" for r in results)

    def test_short_history_redistributes_horizon_weights(self) -> None:
        """100 Tage Historie: 126d/252d/504d nicht verfügbar, nur 5d und 63d.
        Spec §2 Edge-Case: 'Gewicht wird auf verfügbare Horizonte umverteilt'.
        Tickers werden trotz fehlender Long-Horizonte gerankt.
        """
        n = 100
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        market = np.zeros(n)
        a_returns = market + 0.001
        b_returns = market - 0.001

        returns = pd.DataFrame({"A": a_returns, "B": b_returns}, index=index)
        prices = _make_prices(returns)

        results = AlphaModel().run(prices=prices)
        ranks = {r.ticker: r.rank for r in results}
        assert ranks["A"] == 1
        assert ranks["B"] == 2
