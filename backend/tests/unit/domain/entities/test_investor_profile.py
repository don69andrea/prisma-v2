"""Unit-Tests für InvestorProfile Domain Entity."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.domain.entities.investor_profile import InvestorProfile

pytestmark = pytest.mark.unit


def _make_profile(**overrides) -> InvestorProfile:
    defaults = {"session_id": "test-session-abc"}
    defaults.update(overrides)
    return InvestorProfile(**defaults)


class TestInvestorProfileDefaults:
    def test_default_values(self) -> None:
        p = _make_profile()
        assert p.financial_knowledge == "low"
        assert p.investment_goal == "beat_savings"
        assert p.time_horizon == "medium"
        assert p.risk_profile == "moderate"
        assert p.sector_affinity == []
        assert p.known_tickers == []
        assert p.confidence_score == 0.0
        assert p.onboarding_complete is False

    def test_id_is_uuid(self) -> None:
        p = _make_profile()
        assert isinstance(p.id, UUID)

    def test_session_id_is_str(self) -> None:
        p = _make_profile(session_id="my-session-123")
        assert p.session_id == "my-session-123"

    def test_created_at_is_utc_aware(self) -> None:
        p = _make_profile()
        assert p.created_at.tzinfo is not None

    def test_two_profiles_have_different_ids(self) -> None:
        p1 = _make_profile()
        p2 = _make_profile()
        assert p1.id != p2.id


class TestInvestorProfileValidation:
    def test_valid_risk_profiles(self) -> None:
        for rp in ("conservative", "moderate", "aggressive"):
            p = _make_profile(risk_profile=rp)
            assert p.risk_profile == rp

    def test_invalid_risk_profile_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_profile(risk_profile="balanced")  # old value — must fail

    def test_valid_time_horizons(self) -> None:
        for th in ("short", "medium", "long"):
            p = _make_profile(time_horizon=th)
            assert p.time_horizon == th

    def test_valid_investment_goals(self) -> None:
        for g in ("housing", "retirement", "freedom", "beat_savings", "other"):
            p = _make_profile(investment_goal=g)
            assert p.investment_goal == g

    def test_confidence_score_clamped_to_0_1(self) -> None:
        with pytest.raises(ValidationError):
            _make_profile(confidence_score=1.5)
        with pytest.raises(ValidationError):
            _make_profile(confidence_score=-0.1)

    def test_confidence_score_boundaries_valid(self) -> None:
        assert _make_profile(confidence_score=0.0).confidence_score == 0.0
        assert _make_profile(confidence_score=1.0).confidence_score == 1.0

    def test_profession_optional(self) -> None:
        assert _make_profile(profession=None).profession is None
        assert _make_profile(profession="Entwickler").profession == "Entwickler"


class TestInvestorProfileRiskLabel:
    def test_conservative_label(self) -> None:
        p = _make_profile(risk_profile="conservative")
        assert "Konservativ" in p.risk_label

    def test_moderate_label(self) -> None:
        p = _make_profile(risk_profile="moderate")
        assert "Ausgewogen" in p.risk_label

    def test_aggressive_label(self) -> None:
        p = _make_profile(risk_profile="aggressive")
        assert "Wachstumsorientiert" in p.risk_label


class TestInvestorProfileMutability:
    def test_model_copy_update(self) -> None:
        p = _make_profile(risk_profile="moderate")
        updated = p.model_copy(update={"risk_profile": "aggressive"})
        assert updated.risk_profile == "aggressive"
        assert p.risk_profile == "moderate"  # original unchanged

    def test_sector_affinity_list(self) -> None:
        p = _make_profile(sector_affinity=["tech", "pharma"])
        assert "tech" in p.sector_affinity
        assert "pharma" in p.sector_affinity

    def test_known_tickers_list(self) -> None:
        p = _make_profile(known_tickers=["NESN.SW", "ROG.SW"])
        assert len(p.known_tickers) == 2
