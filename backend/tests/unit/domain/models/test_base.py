"""Tests für die gemeinsamen Modell-Typen (ModelRankingResult, QuantModel-Protocol)."""

import pytest
from pydantic import ValidationError

from backend.domain.models.alpha import AlphaModel
from backend.domain.models.base import ModelRankingResult, QuantModel
from backend.domain.models.diversification import DiversificationModel
from backend.domain.models.quality_classic import QualityClassicModel
from backend.domain.models.trend_momentum import TrendMomentumModel
from backend.domain.models.value_alpha_potential import ValueAlphaPotentialModel

pytestmark = pytest.mark.unit


class TestModelRankingResult:
    def test_valid_full_result(self) -> None:
        r = ModelRankingResult(ticker="NESN.SW", score=1.23, rank=1, confidence="high")
        assert r.ticker == "NESN.SW"
        assert r.rank == 1

    def test_no_rank_when_data_insufficient(self) -> None:
        r = ModelRankingResult(ticker="ABBN.SW", score=None, rank=None, confidence="low")
        assert r.score is None
        assert r.rank is None

    def test_default_confidence_is_high(self) -> None:
        r = ModelRankingResult(ticker="ROG.SW", score=0.5, rank=3)
        assert r.confidence == "high"

    def test_invalid_confidence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelRankingResult.model_validate(
                {"ticker": "X", "score": 0.0, "rank": 1, "confidence": "medium-high"}
            )

    def test_is_frozen(self) -> None:
        r = ModelRankingResult(ticker="X", score=1.0, rank=1)
        with pytest.raises(ValidationError):
            r.ticker = "Y"


class TestQuantModelProtocol:
    """Alle 5 Modell-Klassen müssen das QuantModel-Protocol erfüllen."""

    @pytest.mark.parametrize(
        "model",
        [
            QualityClassicModel(),
            AlphaModel(),
            TrendMomentumModel(),
            ValueAlphaPotentialModel(),
            DiversificationModel(),
        ],
    )
    def test_model_implements_protocol(self, model: object) -> None:
        assert isinstance(model, QuantModel)

    @pytest.mark.parametrize(
        ("model", "expected_name", "expected_category"),
        [
            (QualityClassicModel(), "quality_classic", "Quality"),
            (AlphaModel(), "alpha", "Trend"),
            (TrendMomentumModel(), "trend_momentum", "Trend"),
            (ValueAlphaPotentialModel(), "value_alpha_potential", "Value"),
            (DiversificationModel(), "diversification", "Risk"),
        ],
    )
    def test_model_metadata(
        self, model: QuantModel, expected_name: str, expected_category: str
    ) -> None:
        assert model.name == expected_name
        assert model.category == expected_category
