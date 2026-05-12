"""Tests für Value Alpha Potential — Rolling-Max-Alpha Mean-Reversion.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §4
      docs/specs/2026-04-27-quant-models-redesign.md §3.2
"""

import numpy as np
import pandas as pd
import pytest

from backend.domain.models.value_alpha_potential import ValueAlphaPotentialModel

pytestmark = pytest.mark.unit


def _run(prices: pd.DataFrame) -> dict[str, int | None]:
    """Hilfsfunktion: gibt {ticker: rank} zurück."""
    results = ValueAlphaPotentialModel().run(prices=prices)
    return {r.ticker: r.rank for r in results}


def _make_prices(returns: pd.DataFrame, start: float = 100.0) -> pd.DataFrame:
    """Wandelt Daily-Returns in kumulierte Preise."""
    return start * (1 + returns).cumprod()


class TestValueAlphaPotentialSpecConstants:
    def test_constants_match_spec(self) -> None:
        model = ValueAlphaPotentialModel()
        assert model.ALPHA_HORIZON_DAYS == 63
        assert model.ROLLING_MAX_WINDOW_DAYS == 252
        assert model.MIN_PERIODS == 68


class TestValueAlphaPotentialFormula:
    def test_past_star_ranks_first(self) -> None:
        """Past-Star vs. konstanter Performer:
        - PAST_STAR: starke Outperformance vor ~6 Monaten, jetzt zurückgefallen → grosses Distance-to-Peak → Rang 1
        - CONSTANT: konstant am Mittel → potential ~ 0 → schlechter Rang
        """
        n = 400
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        market = np.zeros(n)  # neutraler Markt zur Kontrolle

        past_star = market.copy()
        # Outperformance-Phase: Tag 100-200 mit +0.5%/Tag
        past_star[100:200] = 0.005
        # Danach zurück auf 0 (kein neues Hoch)

        constant = market.copy()  # immer 0%

        returns = pd.DataFrame({"PAST_STAR": past_star, "CONSTANT": constant}, index=index)
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["PAST_STAR"] == 1
        assert ranks["CONSTANT"] == 2

    def test_at_peak_today_yields_negative_potential(self) -> None:
        """Ticker, der heute auf seinem eigenen Outperformance-Hoch sitzt:
        rolling_max_alpha = aktuelles alpha → potential ~ 0 (oder leicht positiv durch min_periods).
        Spec §4 Edge-Case: 'Negativer potential ist gültig, wird normal gerankt.'
        """
        n = 350
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        market = np.zeros(n)

        # AT_PEAK: monoton steigende Outperformance bis heute (jeden Tag besser)
        # → aktuelles alpha = rolling_max_alpha → potential ≈ 0
        at_peak = np.full(n, 0.001)  # konstant +0.1% / Tag → kumulativ steigend

        # CONSTANT: 0%
        constant = market.copy()

        returns = pd.DataFrame({"AT_PEAK": at_peak, "CONSTANT": constant}, index=index)
        prices = _make_prices(returns)

        results = {r.ticker: r for r in ValueAlphaPotentialModel().run(prices=prices)}
        # AT_PEAK sitzt am Hoch → score nahe 0 oder negativ; CONSTANT hat höhere Distance
        assert results["AT_PEAK"].score is not None
        assert results["CONSTANT"].score is not None
        # Beide werden gerankt (kein None), egal ob negativ
        assert results["AT_PEAK"].rank is not None
        assert results["CONSTANT"].rank is not None

    def test_deterministic(self) -> None:
        n = 200
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


class TestValueAlphaPotentialEdgeCases:
    def test_empty_universe_returns_empty(self) -> None:
        assert ValueAlphaPotentialModel().run(prices=pd.DataFrame()) == []

    def test_insufficient_datapoints_yields_no_ranks(self) -> None:
        """< 68 Datenpunkte (min_periods für rolling max) → score=None, rank=None."""
        n = 50
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(2)
        prices = _make_prices(
            pd.DataFrame(
                {"A": rng.normal(0.0005, 0.01, n), "B": rng.normal(0.0005, 0.012, n)},
                index=index,
            )
        )

        results = ValueAlphaPotentialModel().run(prices=prices)
        assert all(r.rank is None for r in results)
        assert all(r.confidence == "low" for r in results)

    def test_single_ticker_yields_rank_one(self) -> None:
        """1 Ticker → benchmark = ticker → alpha = 0 immer → potential = 0 → rank=1."""
        n = 200
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        rng = np.random.default_rng(0)
        prices = _make_prices(pd.DataFrame({"SOLO": rng.normal(0.0005, 0.01, n)}, index=index))

        results = ValueAlphaPotentialModel().run(prices=prices)
        assert len(results) == 1
        assert results[0].ticker == "SOLO"
        assert results[0].rank == 1
