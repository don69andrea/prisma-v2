"""Tests für RankingAggregator — gewichteter Total-Rank aus 5 Modell-Rängen.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §7
"""

from collections.abc import Mapping

import pytest

from backend.application.services.ranking_aggregator import RankingAggregator
from backend.domain.entities.universe import WeightConfig
from backend.domain.models.base import ModelRankingResult

pytestmark = pytest.mark.unit

EQUAL_WEIGHTS = WeightConfig.equal()


def _results(ranks: Mapping[str, int | None]) -> list[ModelRankingResult]:
    return [
        ModelRankingResult(
            ticker=t,
            score=float(r) if r is not None else None,
            rank=r,
            confidence="low" if r is None else "high",
        )
        for t, r in ranks.items()
    ]


def _aggregate(
    model_results: Mapping[str, Mapping[str, int | None]],
    weights: WeightConfig = EQUAL_WEIGHTS,
) -> dict[str, int | None]:
    per_model = {m: _results(ranks) for m, ranks in model_results.items()}
    results = RankingAggregator().aggregate(per_model, weights)
    return {r.ticker: r.total_rank for r in results}


class TestRankingAggregator:
    def test_equal_weights_best_across_models_gets_rank_one(self) -> None:
        model_results = {
            "quality_classic": {"A": 1, "B": 2, "C": 3},
            "alpha": {"A": 1, "B": 2, "C": 3},
            "trend_momentum": {"A": 1, "B": 2, "C": 3},
            "value_alpha_potential": {"A": 1, "B": 2, "C": 3},
            "diversification": {"A": 1, "B": 2, "C": 3},
        }
        ranks = _aggregate(model_results)
        assert ranks["A"] == 1
        assert ranks["B"] == 2
        assert ranks["C"] == 3

    def test_weighted_aggregation_favours_higher_weighted_model(self) -> None:
        # A is best in quality_classic (weight 0.8), worst in others
        # B is worst in quality_classic, best in others
        weights = WeightConfig(
            weights={
                "quality_classic": 0.80,
                "alpha": 0.05,
                "trend_momentum": 0.05,
                "value_alpha_potential": 0.05,
                "diversification": 0.05,
            }
        )
        model_results = {
            "quality_classic": {"A": 1, "B": 2},
            "alpha": {"A": 2, "B": 1},
            "trend_momentum": {"A": 2, "B": 1},
            "value_alpha_potential": {"A": 2, "B": 1},
            "diversification": {"A": 2, "B": 1},
        }
        ranks = _aggregate(model_results, weights)
        assert ranks["A"] == 1
        assert ranks["B"] == 2

    def test_missing_model_rank_redistributes_weight(self) -> None:
        # A hat kein alpha-Rang — Gewicht wird auf andere Modelle verteilt
        model_results = {
            "quality_classic": {"A": 1, "B": 2},
            "alpha": {"B": 1},  # A fehlt
            "trend_momentum": {"A": 1, "B": 2},
            "value_alpha_potential": {"A": 1, "B": 2},
            "diversification": {"A": 1, "B": 2},
        }
        ranks = _aggregate(model_results)
        assert ranks["A"] == 1
        assert ranks["B"] == 2

    def test_ticker_with_all_none_ranks_gets_none(self) -> None:
        model_results = {
            "quality_classic": {"A": 1, "B": None},
            "alpha": {"A": 1, "B": None},
            "trend_momentum": {"A": 1, "B": None},
            "value_alpha_potential": {"A": 1, "B": None},
            "diversification": {"A": 1, "B": None},
        }
        ranks = _aggregate(model_results)
        assert ranks["A"] == 1
        assert ranks["B"] is None

    def test_empty_input_returns_empty(self) -> None:
        assert _aggregate({}) == {}

    def test_deterministic(self) -> None:
        model_results = {
            "quality_classic": {"A": 2, "B": 1, "C": 3},
            "alpha": {"A": 1, "B": 3, "C": 2},
            "trend_momentum": {"A": 3, "B": 2, "C": 1},
            "value_alpha_potential": {"A": 1, "B": 2, "C": 3},
            "diversification": {"A": 2, "B": 1, "C": 3},
        }
        assert _aggregate(model_results) == _aggregate(model_results)


class TestSweetSpot:
    def test_top25_in_3_of_5_models_is_sweet_spot(self) -> None:
        # Universum mit 4 Tickers → Top 25% = Rang 1
        model_results = {
            "quality_classic": {"A": 1, "B": 2, "C": 3, "D": 4},
            "alpha": {"A": 1, "B": 2, "C": 3, "D": 4},
            "trend_momentum": {"A": 1, "B": 2, "C": 3, "D": 4},
            "value_alpha_potential": {"A": 4, "B": 3, "C": 2, "D": 1},
            "diversification": {"A": 4, "B": 3, "C": 2, "D": 1},
        }
        per_model = {m: _results(ranks) for m, ranks in model_results.items()}
        results = RankingAggregator().aggregate(per_model, EQUAL_WEIGHTS)
        by_ticker = {r.ticker: r for r in results}
        assert by_ticker["A"].is_sweet_spot is True  # Top-25% in 3/5
        assert by_ticker["D"].is_sweet_spot is False
