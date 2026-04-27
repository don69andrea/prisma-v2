"""Skeleton-Tests für Alpha.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §6.3
"""

import pytest

from backend.domain.models.alpha import AlphaModel

pytestmark = pytest.mark.unit


class TestAlphaSkeleton:
    def test_run_raises_not_implemented(self) -> None:
        model = AlphaModel()
        with pytest.raises(NotImplementedError):
            model.run(prices=None)


@pytest.mark.skip(reason="Implementation pending — golden dataset + horizon-weights")
class TestAlphaFormula:
    """TODO sobald Implementation steht:

    - Konstantes Outperformance-Profil (z.B. +2% pro Horizont) → erwarteter Score = Σ Gewichte × 0.02
    - Stock identisch zum Benchmark → Alpha-Score 0, Rang im Mittelfeld
    - Sharpe-Bonus: hochvolatile Outperformance vs. stabile gleichgrosse → stabile gewinnt
    - Edge Case: < 504 Handelstage Historie (2J fehlen) → confidence='low'
    """

    def test_horizon_weights_sum_to_one(self) -> None:
        raise NotImplementedError
