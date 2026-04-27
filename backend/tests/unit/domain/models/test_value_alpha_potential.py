"""Skeleton-Tests für Value Alpha Potential.

Spec: docs/specs/2026-04-27-quant-models-redesign.md §3.2
"""

import pytest

from backend.domain.models.value_alpha_potential import ValueAlphaPotentialModel

pytestmark = pytest.mark.unit


class TestValueAlphaPotentialSkeleton:
    def test_run_raises_not_implemented(self) -> None:
        model = ValueAlphaPotentialModel()
        with pytest.raises(NotImplementedError):
            model.run(prices=None)

    def test_constants_match_spec(self) -> None:
        model = ValueAlphaPotentialModel()
        assert model.ALPHA_HORIZON_DAYS == 63
        assert model.ROLLING_MAX_WINDOW_DAYS == 252
        assert model.MIN_PERIODS == 68


@pytest.mark.skip(reason="Implementation pending — pandas + golden dataset")
class TestValueAlphaPotentialFormula:
    """TODO sobald Implementation steht:

    Golden-Dataset-Szenarien (5 Tickers × 600 Tage):
    - Past-Star, jetzt gefallen (Alpha-Peak vor 6 Monaten +8pp, aktuell 0pp) → Rang 1
    - Konstant guter Performer (Alpha stabil +5pp) → potential = 0 → schlechter Rang
    - Underperformer mit Peak knapp über Mittel (Peak +1pp, aktuell -3pp) → potential 4pp, Mittelfeld

    Edge Cases:
    - Aktueller Alpha > rolling_max (heutiger Peak) → potential negativ → wird trotzdem geranked
    - < 68 Datenpunkte → score=None, rank=None, confidence='low'
    - Ticker mit nur konstanten Preisen → alpha = 0 die ganze Zeit → potential = 0

    Spec-Lücke (siehe Spec §10): Alpha-Horizont 63d ist Wahl, nicht definiert.
    Test-Hyperparameter sollten als Konstanten zugänglich sein für Sensitivitäts-Backtest.
    """

    def test_past_star_ranks_first(self) -> None:
        raise NotImplementedError

    def test_negative_potential_still_ranked(self) -> None:
        raise NotImplementedError
