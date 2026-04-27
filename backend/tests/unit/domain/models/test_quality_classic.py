"""Skeleton-Tests für Quality Classic.

Vollständige Tests folgen mit der Implementation.
Spec: docs/specs/2026-04-21-prisma-capstone-design.md §6.1
"""

import pytest

from backend.domain.models.quality_classic import QualityClassicModel

pytestmark = pytest.mark.unit


class TestQualityClassicSkeleton:
    def test_run_raises_not_implemented(self) -> None:
        model = QualityClassicModel()
        with pytest.raises(NotImplementedError):
            model.run(fundamentals=None)


@pytest.mark.skip(reason="Implementation pending — golden dataset + formula")
class TestQualityClassicFormula:
    """TODO: Z-Score je Kennzahl, gleichgewichtetes Mittel, Rang aufsteigend.

    Erwartete Tests sobald Implementation steht:
    - Goldenes Dataset: 5 Tickers × 8 Kennzahlen → erwartete Ränge 1..5
    - Edge Case: ein Ticker hat fehlende Kennzahl → Score nur aus den vorhandenen 7 (oder rank=None)
    - Determinismus: zweimal gleicher Input → identisches Output
    - Kategorie-Bias: alle Kennzahlen identisch → alle Ränge gleich (ties via method='min')
    """

    def test_golden_dataset(self) -> None:
        raise NotImplementedError
