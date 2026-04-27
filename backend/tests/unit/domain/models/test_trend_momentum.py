"""Skeleton-Tests für Trend Momentum.

Spec: docs/specs/2026-04-27-quant-models-redesign.md §3.1
"""

import pytest

from backend.domain.models.trend_momentum import TrendMomentumModel

pytestmark = pytest.mark.unit


class TestTrendMomentumSkeleton:
    def test_run_raises_not_implemented(self) -> None:
        model = TrendMomentumModel()
        with pytest.raises(NotImplementedError):
            model.run(prices=None)

    def test_constants_match_spec(self) -> None:
        model = TrendMomentumModel()
        assert model.HALFLIFE_DAYS == 63
        assert model.MIN_PERIODS == 32


@pytest.mark.skip(reason="Implementation pending — pandas + golden dataset")
class TestTrendMomentumFormula:
    """TODO sobald Implementation steht:

    Golden-Dataset-Szenarien (5 Tickers × 500 Tage synthetische Preise):
    - Outperformer (+0.1% pro Tag relativ zum Mittel) → Rang 1
    - Underperformer (-0.1% pro Tag relativ) → Rang 5
    - Mittelfeld konstant → Rang 3, Score nahe 0
    - Recent-Spike (Underperformer letzte 30 Tage stark) → besser geranked als Long-Term-Underperformer (EWMA-Gewichtung)

    Edge Cases:
    - < 32 Datenpunkte (`min_periods`) → score=None, rank=None, confidence='low'
    - 1 Ticker im Universum → Benchmark = Stock → relative_return = 0 → undefined ranking
    - NaN in Preisdaten → forward-fill oder skip-day, dokumentieren

    Determinismus: gleiche Preistabelle → identische Ränge.
    """

    def test_outperformer_ranks_first(self) -> None:
        raise NotImplementedError

    def test_recent_outperformance_weighted_higher(self) -> None:
        raise NotImplementedError
