"""Unit-Tests für ResearchMemoSchema (LLM-Output-Vertrag)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from backend.domain.entities.research_memo import ContradictionItem
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema

pytestmark = pytest.mark.unit


def _valid_payload() -> dict[str, Any]:
    return {
        "ticker": "NESN",
        "total_rank": 12,
        "one_liner": "Solides Quality-Profil mit moderatem Trend.",
        "ranking_interpretation": "x" * 200,
        "sweet_spot": False,
        "sweet_spot_explanation": None,
        "contradictions": [],
        "key_strengths": ["Stabilität", "Dividende"],
        "key_risks": ["FX-Exposure"],
        "confidence": "medium",
        "generated_at": datetime.now(UTC),
        "model_version": "claude-sonnet-4-6@20260101",
    }


class TestValidConstruct:
    def test_minimal_valid(self) -> None:
        schema = ResearchMemoSchema(**_valid_payload())
        assert schema.ticker == "NESN"
        assert schema.confidence == "medium"

    def test_with_contradictions(self) -> None:
        payload = _valid_payload()
        payload["contradictions"] = [
            ContradictionItem(model_a="Quality", model_b="Trend", description="x" * 50),
        ]
        schema = ResearchMemoSchema(**payload)
        assert len(schema.contradictions) == 1


class TestStringLengthConstraints:
    def test_one_liner_too_short(self) -> None:
        payload = _valid_payload()
        payload["one_liner"] = "x" * 9  # min=10
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_one_liner_too_long(self) -> None:
        payload = _valid_payload()
        payload["one_liner"] = "x" * 151
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_ranking_interpretation_too_short(self) -> None:
        payload = _valid_payload()
        payload["ranking_interpretation"] = "x" * 99  # min=100
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_ranking_interpretation_too_long(self) -> None:
        payload = _valid_payload()
        payload["ranking_interpretation"] = "x" * 1001  # max=1000
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_sweet_spot_explanation_too_long(self) -> None:
        payload = _valid_payload()
        payload["sweet_spot_explanation"] = "x" * 301
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)


class TestListConstraints:
    def test_contradictions_max_3(self) -> None:
        payload = _valid_payload()
        payload["contradictions"] = [
            ContradictionItem(model_a=f"M{i}", model_b="X", description="x" * 50) for i in range(4)
        ]
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_key_strengths_min_1(self) -> None:
        payload = _valid_payload()
        payload["key_strengths"] = []
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_key_strengths_max_5(self) -> None:
        payload = _valid_payload()
        payload["key_strengths"] = ["a", "b", "c", "d", "e", "f"]
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)


class TestEnumLikeFields:
    def test_confidence_must_be_valid_literal(self) -> None:
        payload = _valid_payload()
        payload["confidence"] = "very_high"
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)

    def test_total_rank_must_be_positive(self) -> None:
        payload = _valid_payload()
        payload["total_rank"] = 0
        with pytest.raises(ValidationError):
            ResearchMemoSchema(**payload)
