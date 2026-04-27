"""Unit-Tests für Universe-Entity und WeightConfig-Value-Object."""

import uuid

import pytest
from pydantic import ValidationError

from backend.domain.entities.universe import Universe, WeightConfig

pytestmark = pytest.mark.unit

VALID_WEIGHTS = {
    "quality_classic": 0.20,
    "alpha": 0.20,
    "trend_momentum": 0.20,
    "value_alpha_potential": 0.20,
    "diversification": 0.20,
}


class TestWeightConfig:
    def test_valid_weights_accepted(self) -> None:
        wc = WeightConfig(weights=VALID_WEIGHTS)
        assert abs(sum(wc.weights.values()) - 1.0) < 1e-6

    def test_equal_factory(self) -> None:
        wc = WeightConfig.equal()
        assert set(wc.weights.keys()) == {
            "quality_classic",
            "alpha",
            "trend_momentum",
            "value_alpha_potential",
            "diversification",
        }
        assert abs(sum(wc.weights.values()) - 1.0) < 1e-6

    def test_weights_not_summing_to_one_raises(self) -> None:
        bad = {**VALID_WEIGHTS, "quality_classic": 0.50}
        with pytest.raises(ValidationError, match="1.0"):
            WeightConfig(weights=bad)

    def test_unknown_model_name_raises(self) -> None:
        bad = {**VALID_WEIGHTS, "quality_classic": 0.0, "unknown_model": 0.20}
        with pytest.raises(ValidationError, match="Unbekannte Modell-Namen"):
            WeightConfig(weights=bad)

    def test_weight_config_is_immutable(self) -> None:
        wc = WeightConfig(weights=VALID_WEIGHTS)
        with pytest.raises((ValidationError, TypeError)):
            wc.weights = {}


class TestUniverse:
    def _make(self, **overrides: object) -> Universe:
        defaults: dict[str, object] = {
            "id": uuid.uuid4(),
            "name": "SMI",
            "tickers": ["NESN", "ROG", "NOVN"],
            "region": "CH",
        }
        defaults.update(overrides)
        return Universe(**defaults)  # type: ignore[arg-type]

    def test_valid_universe_created(self) -> None:
        u = self._make()
        assert u.name == "SMI"
        assert "NESN" in u.tickers

    def test_tickers_uppercased(self) -> None:
        u = self._make(tickers=["nesn", "rog"])
        assert u.tickers == ("NESN", "ROG")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="leer"):
            self._make(name="   ")

    def test_universe_is_immutable(self) -> None:
        u = self._make()
        with pytest.raises((ValidationError, TypeError)):
            u.name = "DAX"
