"""Unit-Tests für die LLM-Pricing-Konstanten.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §6.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.infrastructure.llm.pricing import PRICING, ModelPricing

pytestmark = pytest.mark.unit


class TestModelPricing:
    def test_is_frozen_dataclass(self) -> None:
        pricing = ModelPricing(
            input_per_mtok=Decimal("3.00"),
            output_per_mtok=Decimal("15.00"),
            embed_per_mtok=None,
        )
        with pytest.raises(FrozenInstanceError):
            pricing.input_per_mtok = Decimal("99.00")  # type: ignore[misc]

    def test_fields_are_decimal(self) -> None:
        pricing = ModelPricing(
            input_per_mtok=Decimal("3.00"),
            output_per_mtok=Decimal("15.00"),
            embed_per_mtok=Decimal("0.18"),
        )
        assert isinstance(pricing.input_per_mtok, Decimal)
        assert isinstance(pricing.output_per_mtok, Decimal)
        assert isinstance(pricing.embed_per_mtok, Decimal)

    def test_embed_field_can_be_none(self) -> None:
        pricing = ModelPricing(
            input_per_mtok=Decimal("3.00"),
            output_per_mtok=Decimal("15.00"),
            embed_per_mtok=None,
        )
        assert pricing.embed_per_mtok is None


class TestPricingRegistry:
    def test_contains_all_required_models(self) -> None:
        # Modelle gemäss ADR-0002 (Sonnet/Haiku) + ADR-0004 §4 (Voyage)
        assert "claude-sonnet-4-6" in PRICING
        assert "claude-haiku-4-5" in PRICING
        assert "voyage-3-large" in PRICING

    def test_claude_models_have_input_and_output_pricing(self) -> None:
        for model_name in ("claude-sonnet-4-6", "claude-haiku-4-5"):
            pricing = PRICING[model_name]
            assert pricing.input_per_mtok is not None, f"{model_name}: input"
            assert pricing.output_per_mtok is not None, f"{model_name}: output"
            assert pricing.input_per_mtok > Decimal("0"), f"{model_name}: input"
            assert pricing.output_per_mtok > Decimal("0"), f"{model_name}: output"
            assert pricing.embed_per_mtok is None, f"{model_name}: embed"

    def test_voyage_has_embed_pricing(self) -> None:
        pricing = PRICING["voyage-3-large"]
        assert pricing.embed_per_mtok is not None
        assert pricing.embed_per_mtok > Decimal("0")

    def test_voyage_chat_pricing_is_none(self) -> None:
        """Voyage ist ein Embedding-only-Modell — Chat-Pricing muss None sein,
        nicht Decimal('0'). 'None' = "trifft nicht zu", '0' wäre "kostenlos"."""
        pricing = PRICING["voyage-3-large"]
        assert pricing.input_per_mtok is None
        assert pricing.output_per_mtok is None

    def test_no_float_values_anywhere(self) -> None:
        # CLAUDE.md-Regel: keine Floats für Geldbeträge
        for model_name, pricing in PRICING.items():
            for field_value in (
                pricing.input_per_mtok,
                pricing.output_per_mtok,
                pricing.embed_per_mtok,
            ):
                if field_value is not None:
                    assert isinstance(field_value, Decimal), model_name
