"""Skeleton-Tests für Diversification.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §6.5
"""

import pytest

from backend.domain.models.diversification import DiversificationModel

pytestmark = pytest.mark.unit


class TestDiversificationSkeleton:
    def test_run_raises_not_implemented(self) -> None:
        model = DiversificationModel()
        with pytest.raises(NotImplementedError):
            model.run(prices=None)


@pytest.mark.skip(reason="Implementation pending — Ledoit-Wolf + golden dataset")
class TestDiversificationFormula:
    """TODO sobald Implementation steht:

    - Stock mit niedriger Volatilität + niedrige durchschnittliche Korrelation → Rang 1
    - Stock mit identischer Bewegung wie alle anderen (Korrelation ~1) → schlechter Rang
    - Hochvolatile aber unkorrelierte Aktie vs. niedrigvolatile aber stark korrelierte → harmonisches Mittel entscheidet

    Edge Cases:
    - Nur 1 Ticker → keine Diversifikations-Aussage möglich → rank=None
    - Konstante Preise (Vol = 0) → 1/Vol divergiert → score=None mit Begründung
    """

    def test_uncorrelated_low_vol_ranks_first(self) -> None:
        raise NotImplementedError
