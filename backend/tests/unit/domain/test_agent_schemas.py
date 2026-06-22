"""Tests for agent output Pydantic schemas (D-05 contract lock).

TDD RED phase: These tests are written BEFORE agent_schemas.py exists.
They verify:
  - All 8 schemas are importable from one module
  - All Literal fields reject out-of-enum values (no-freetext / D-06 test 5)
  - All bounded floats reject out-of-range values
  - TradeSignal carries audit_trail_id (UUID) and per-layer rationale
  - Default disclaimer is the exact German string
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Import all 8 schemas — RED: this fails until agent_schemas.py is created
# ---------------------------------------------------------------------------
from backend.domain.schemas.agent_schemas import (  # noqa: E402
    BearCase,
    BullCase,
    MacroRegime,
    OnChainView,
    RiskVerdict,
    SentimentLLMOutput,
    SentimentView,
    TechnicalView,
    TradeSignal,
)

# ---------------------------------------------------------------------------
# TechnicalView
# ---------------------------------------------------------------------------


class TestTechnicalView:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "coin": "BTC",
            "stance": "BULLISH",
            "consensus": "3/3",
            "key_signals": ["MA crossover", "MACD bullish"],
            "confidence": 0.85,
            "reasoning": "All indicators align.",
        }
        base.update(overrides)
        return base

    def test_valid_bullish(self) -> None:
        view = TechnicalView(**self._valid())
        assert view.coin == "BTC"
        assert view.stance == "BULLISH"
        assert view.confidence == 0.85

    def test_valid_neutral(self) -> None:
        view = TechnicalView(**self._valid(stance="NEUTRAL"))
        assert view.stance == "NEUTRAL"

    def test_valid_bearish(self) -> None:
        view = TechnicalView(**self._valid(stance="BEARISH"))
        assert view.stance == "BEARISH"

    def test_invalid_stance_freetext(self) -> None:
        """D-06 test 5: Literal field rejects out-of-enum value."""
        with pytest.raises(ValidationError):
            TechnicalView(**self._valid(stance="VERY_BULLISH"))

    def test_confidence_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TechnicalView(**self._valid(confidence=1.5))

    def test_confidence_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            TechnicalView(**self._valid(confidence=-0.1))

    def test_confidence_boundary_zero(self) -> None:
        view = TechnicalView(**self._valid(confidence=0.0))
        assert view.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        view = TechnicalView(**self._valid(confidence=1.0))
        assert view.confidence == 1.0


# ---------------------------------------------------------------------------
# OnChainView
# ---------------------------------------------------------------------------


class TestOnChainView:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "coin": "BTC",
            "valuation": "CHEAP",
            "network_health": "STRONG",
            "confidence": 0.7,
            "reasoning": "MVRV-Z below 1.",
        }
        base.update(overrides)
        return base

    def test_valid_cheap_strong(self) -> None:
        view = OnChainView(**self._valid())
        assert view.valuation == "CHEAP"
        assert view.network_health == "STRONG"

    def test_valid_fair_neutral(self) -> None:
        view = OnChainView(**self._valid(valuation="FAIR", network_health="NEUTRAL"))
        assert view.valuation == "FAIR"
        assert view.network_health == "NEUTRAL"

    def test_valid_expensive_weak(self) -> None:
        view = OnChainView(**self._valid(valuation="EXPENSIVE", network_health="WEAK"))
        assert view.valuation == "EXPENSIVE"
        assert view.network_health == "WEAK"

    def test_invalid_valuation_freetext(self) -> None:
        """D-06 test 5: Literal field rejects out-of-enum value."""
        with pytest.raises(ValidationError):
            OnChainView(**self._valid(valuation="OVERVALUED"))

    def test_invalid_network_health_freetext(self) -> None:
        """D-06 test 5: Literal field rejects out-of-enum value."""
        with pytest.raises(ValidationError):
            OnChainView(**self._valid(network_health="EXCELLENT"))

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            OnChainView(**self._valid(confidence=1.1))


# ---------------------------------------------------------------------------
# SentimentView
# ---------------------------------------------------------------------------


class TestSentimentView:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "coin": "BTC",
            "score": 0.3,
            "regime": "GREED",
            "reasoning": "Fear&Greed 65 (Greed).",
        }
        base.update(overrides)
        return base

    def test_valid_defaults(self) -> None:
        view = SentimentView(**self._valid())
        assert view.news_surprise is None
        assert view.veto is False
        assert view.sources == []

    def test_valid_fear_regime(self) -> None:
        view = SentimentView(**self._valid(score=-0.5, regime="FEAR"))
        assert view.regime == "FEAR"
        assert view.score == -0.5

    def test_valid_neutral_regime(self) -> None:
        view = SentimentView(**self._valid(score=0.0, regime="NEUTRAL"))
        assert view.regime == "NEUTRAL"

    def test_invalid_regime_freetext(self) -> None:
        """D-06 test 5: Literal field rejects out-of-enum value."""
        with pytest.raises(ValidationError):
            SentimentView(**self._valid(regime="EXTREME_FEAR"))

    def test_score_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            SentimentView(**self._valid(score=1.1))

    def test_score_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            SentimentView(**self._valid(score=-1.1))

    def test_score_boundary_values(self) -> None:
        view_neg = SentimentView(**self._valid(score=-1.0, regime="FEAR"))
        assert view_neg.score == -1.0
        view_pos = SentimentView(**self._valid(score=1.0))
        assert view_pos.score == 1.0

    def test_news_surprise_explicit_true(self) -> None:
        view = SentimentView(**self._valid(news_surprise=True))
        assert view.news_surprise is True

    def test_veto_can_be_true(self) -> None:
        view = SentimentView(**self._valid(veto=True))
        assert view.veto is True

    def test_sources_list(self) -> None:
        view = SentimentView(**self._valid(sources=["CoinGlass", "CryptoQuant"]))
        assert view.sources == ["CoinGlass", "CryptoQuant"]


# ---------------------------------------------------------------------------
# MacroRegime
# ---------------------------------------------------------------------------


class TestMacroRegime:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "regime": "RISK_ON",
            "drivers": ["Low real rates", "DXY weakness"],
            "confidence": 0.75,
            "reasoning": "Fed pivot signals risk-on environment.",
        }
        base.update(overrides)
        return base

    def test_valid_risk_on(self) -> None:
        macro = MacroRegime(**self._valid())
        assert macro.regime == "RISK_ON"

    def test_valid_neutral(self) -> None:
        macro = MacroRegime(**self._valid(regime="NEUTRAL"))
        assert macro.regime == "NEUTRAL"

    def test_valid_risk_off(self) -> None:
        macro = MacroRegime(**self._valid(regime="RISK_OFF"))
        assert macro.regime == "RISK_OFF"

    def test_invalid_regime_freetext(self) -> None:
        """D-06 test 5: Literal field rejects out-of-enum value."""
        with pytest.raises(ValidationError):
            MacroRegime(**self._valid(regime="EXTREME_RISK_OFF"))

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            MacroRegime(**self._valid(confidence=1.5))

    def test_confidence_boundary_values(self) -> None:
        macro_low = MacroRegime(**self._valid(confidence=0.0))
        assert macro_low.confidence == 0.0
        macro_high = MacroRegime(**self._valid(confidence=1.0))
        assert macro_high.confidence == 1.0

    def test_drivers_list(self) -> None:
        macro = MacroRegime(**self._valid(drivers=["Rising DXY"]))
        assert macro.drivers == ["Rising DXY"]


# ---------------------------------------------------------------------------
# BullCase
# ---------------------------------------------------------------------------


class TestBullCase:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "thesis": "BTC poised for rally on ETF inflows.",
            "strongest_points": ["Institutional demand", "Supply shock post-halving"],
            "risks_acknowledged": ["Regulatory risk", "Macro headwinds"],
        }
        base.update(overrides)
        return base

    def test_valid(self) -> None:
        bull = BullCase(**self._valid())
        assert bull.thesis == "BTC poised for rally on ETF inflows."
        assert len(bull.strongest_points) == 2
        assert len(bull.risks_acknowledged) == 2

    def test_empty_lists_allowed(self) -> None:
        bull = BullCase(**self._valid(strongest_points=[], risks_acknowledged=[]))
        assert bull.strongest_points == []
        assert bull.risks_acknowledged == []


# ---------------------------------------------------------------------------
# BearCase
# ---------------------------------------------------------------------------


class TestBearCase:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "thesis": "BTC faces headwinds from tighter liquidity.",
            "strongest_points": ["Rising real rates", "Exchange outflows slowing"],
            "counter_to_bull": ["ETF inflows already priced in"],
        }
        base.update(overrides)
        return base

    def test_valid(self) -> None:
        bear = BearCase(**self._valid())
        assert bear.thesis == "BTC faces headwinds from tighter liquidity."
        assert len(bear.counter_to_bull) == 1

    def test_empty_lists_allowed(self) -> None:
        bear = BearCase(**self._valid(strongest_points=[], counter_to_bull=[]))
        assert bear.strongest_points == []
        assert bear.counter_to_bull == []


# ---------------------------------------------------------------------------
# RiskVerdict
# ---------------------------------------------------------------------------


class TestRiskVerdict:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "approve": True,
            "max_size": 1.0,
            "breaches": [],
            "reasoning": "Portfolio within risk limits.",
        }
        base.update(overrides)
        return base

    def test_valid_approved(self) -> None:
        rv = RiskVerdict(**self._valid())
        assert rv.approve is True
        assert rv.max_size == 1.0

    def test_valid_rejected(self) -> None:
        rv = RiskVerdict(
            **self._valid(approve=False, max_size=0.0, breaches=["Concentration > 20%"])
        )
        assert rv.approve is False
        assert rv.max_size == 0.0

    def test_max_size_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            RiskVerdict(**self._valid(max_size=1.6))

    def test_max_size_negative(self) -> None:
        with pytest.raises(ValidationError):
            RiskVerdict(**self._valid(max_size=-0.1))

    def test_max_size_boundary_zero(self) -> None:
        rv = RiskVerdict(**self._valid(max_size=0.0))
        assert rv.max_size == 0.0

    def test_max_size_boundary_1_5(self) -> None:
        rv = RiskVerdict(**self._valid(max_size=1.5))
        assert rv.max_size == 1.5

    def test_breaches_list(self) -> None:
        rv = RiskVerdict(**self._valid(breaches=["Max drawdown exceeded", "Position limit"]))
        assert len(rv.breaches) == 2


# ---------------------------------------------------------------------------
# TradeSignal
# ---------------------------------------------------------------------------

_EXPECTED_DISCLAIMER = "Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."


class TestTradeSignal:
    def _valid(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "coin": "BTC",
            "action": "BUY",
            "size_factor": 0.8,
            "confidence": 0.75,
            "rationale_by_layer": {
                "technical": "Bullish momentum.",
                "onchain": "MVRV-Z cheap.",
                "sentiment": "Greed 65.",
                "macro": "Risk-on regime.",
                "bull": "ETF inflows accelerating.",
                "bear": "Regulatory risk remains.",
                "risk": "Within limits.",
            },
            "audit_trail_id": uuid.uuid4(),
        }
        base.update(overrides)
        return base

    def test_valid_buy(self) -> None:
        signal = TradeSignal(**self._valid())
        assert signal.action == "BUY"
        assert signal.size_factor == 0.8

    def test_valid_hold(self) -> None:
        signal = TradeSignal(**self._valid(action="HOLD", size_factor=0.0))
        assert signal.action == "HOLD"

    def test_valid_sell(self) -> None:
        signal = TradeSignal(**self._valid(action="SELL", size_factor=0.0))
        assert signal.action == "SELL"

    def test_invalid_action_freetext(self) -> None:
        """D-06 test 5: Literal field rejects out-of-enum value."""
        with pytest.raises(ValidationError):
            TradeSignal(**self._valid(action="STRONG_BUY"))

    def test_size_factor_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TradeSignal(**self._valid(size_factor=1.6))

    def test_size_factor_negative(self) -> None:
        with pytest.raises(ValidationError):
            TradeSignal(**self._valid(size_factor=-0.1))

    def test_size_factor_boundary_zero(self) -> None:
        signal = TradeSignal(**self._valid(size_factor=0.0))
        assert signal.size_factor == 0.0

    def test_size_factor_boundary_1_5(self) -> None:
        signal = TradeSignal(**self._valid(size_factor=1.5))
        assert signal.size_factor == 1.5

    def test_confidence_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TradeSignal(**self._valid(confidence=1.5))

    def test_confidence_boundary_values(self) -> None:
        signal_low = TradeSignal(**self._valid(confidence=0.0))
        assert signal_low.confidence == 0.0
        signal_high = TradeSignal(**self._valid(confidence=1.0))
        assert signal_high.confidence == 1.0

    def test_audit_trail_id_is_uuid(self) -> None:
        trail_id = uuid.uuid4()
        signal = TradeSignal(**self._valid(audit_trail_id=trail_id))
        assert isinstance(signal.audit_trail_id, uuid.UUID)
        assert signal.audit_trail_id == trail_id

    def test_audit_trail_id_required(self) -> None:
        """audit_trail_id must NOT be optional."""
        data = self._valid()
        del data["audit_trail_id"]
        with pytest.raises(ValidationError):
            TradeSignal(**data)

    def test_rationale_by_layer_is_dict_str_str(self) -> None:
        signal = TradeSignal(**self._valid())
        assert isinstance(signal.rationale_by_layer, dict)
        for k, v in signal.rationale_by_layer.items():
            assert isinstance(k, str)
            assert isinstance(v, str)

    def test_default_disclaimer_exact_german(self) -> None:
        signal = TradeSignal(**self._valid())
        assert signal.disclaimer == _EXPECTED_DISCLAIMER

    def test_default_disclaimer_non_empty(self) -> None:
        signal = TradeSignal(**self._valid())
        assert len(signal.disclaimer) > 0

    def test_audit_trail_id_accepts_uuid_string(self) -> None:
        """Pydantic should coerce a valid UUID string to uuid.UUID."""
        trail_id = str(uuid.uuid4())
        signal = TradeSignal(**self._valid(audit_trail_id=trail_id))
        assert isinstance(signal.audit_trail_id, uuid.UUID)

    def test_no_shorting_sell_implies_zero_size(self) -> None:
        """Verify that a SELL signal with size_factor=0.0 is valid (no negative)."""
        signal = TradeSignal(**self._valid(action="SELL", size_factor=0.0))
        assert signal.action == "SELL"
        assert signal.size_factor == 0.0
        assert signal.size_factor >= 0.0


# ---------------------------------------------------------------------------
# SentimentLLMOutput (Phase 04-01 — D-04 / §0 Iron Rule)
# ---------------------------------------------------------------------------


class TestSentimentLLMOutput:
    """SentimentLLMOutput must have exactly news_surprise: bool + reasoning: str.

    §0 Iron Rule: LLM never produces a number. No score, veto, or regime field.
    """

    def test_valid_news_surprise_true(self) -> None:
        """SentimentLLMOutput(news_surprise=True, reasoning='x').news_surprise is True."""
        out = SentimentLLMOutput(news_surprise=True, reasoning="Hack detected.")
        assert out.news_surprise is True

    def test_valid_news_surprise_false(self) -> None:
        out = SentimentLLMOutput(news_surprise=False, reasoning="No significant event.")
        assert out.news_surprise is False

    def test_valid_reasoning_preserved(self) -> None:
        out = SentimentLLMOutput(news_surprise=True, reasoning="BTC regulation shock.")
        assert out.reasoning == "BTC regulation shock."

    def test_non_bool_news_surprise_raises_validation_error(self) -> None:
        """§0 Iron Rule: LLM must not emit a string like 'maybe' for a bool field."""
        with pytest.raises(ValidationError):
            SentimentLLMOutput(news_surprise="maybe", reasoning="x")  # type: ignore[arg-type]

    def test_integer_news_surprise_is_coerced_or_rejected(self) -> None:
        """Pydantic strict bool: integer 1/0 must raise ValidationError (not coerce)."""
        with pytest.raises(ValidationError):
            SentimentLLMOutput(news_surprise=1, reasoning="x")  # type: ignore[arg-type]

    def test_has_no_score_field(self) -> None:
        """§0 Iron Rule: no numeric score field allowed on SentimentLLMOutput."""
        out = SentimentLLMOutput(news_surprise=True, reasoning="x")
        assert not hasattr(out, "score"), "score field must NOT exist on SentimentLLMOutput"

    def test_has_no_veto_field(self) -> None:
        """§0 Iron Rule: no veto field on SentimentLLMOutput (veto is Python rule-set)."""
        out = SentimentLLMOutput(news_surprise=True, reasoning="x")
        assert not hasattr(out, "veto"), "veto field must NOT exist on SentimentLLMOutput"

    def test_has_no_regime_field(self) -> None:
        """§0 Iron Rule: no regime field on SentimentLLMOutput (regime is computed)."""
        out = SentimentLLMOutput(news_surprise=True, reasoning="x")
        assert not hasattr(out, "regime"), "regime field must NOT exist on SentimentLLMOutput"

    def test_exactly_two_fields(self) -> None:
        """SentimentLLMOutput has exactly news_surprise and reasoning — no other data fields."""
        out = SentimentLLMOutput(news_surprise=False, reasoning="y")
        field_names = set(out.model_fields.keys())
        assert field_names == {"news_surprise", "reasoning"}
