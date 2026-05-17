"""Unit-Tests für ContradictionItem Value-Object (ResearchMemo)."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo

pytestmark = pytest.mark.unit


class TestContradictionItem:
    def test_valid_construct(self) -> None:
        item = ContradictionItem(
            model_a="Quality Classic",
            model_b="Diversification",
            description="Top in Quality, schwach in Risiko-Diversifikation.",
        )
        assert item.model_a == "Quality Classic"

    def test_is_frozen(self) -> None:
        """Pydantic v2 frozen erzwingt Immutability via ValidationError beim setattr."""
        item = ContradictionItem(model_a="A", model_b="B", description="x" * 50)
        with pytest.raises(ValidationError):
            item.model_a = "C"

    def test_description_max_length_200(self) -> None:
        with pytest.raises(ValidationError):
            ContradictionItem(model_a="A", model_b="B", description="x" * 201)

    def test_model_a_min_length_1(self) -> None:
        with pytest.raises(ValidationError):
            ContradictionItem(model_a="", model_b="B", description="x" * 50)

    def test_model_a_max_length_64(self) -> None:
        with pytest.raises(ValidationError):
            ContradictionItem(model_a="x" * 65, model_b="B", description="x" * 50)


def _valid_entity_payload(**overrides: Any) -> dict[str, Any]:
    """Default valid payload für ResearchMemo. Override via kwargs."""
    payload: dict[str, Any] = {
        "id": uuid4(),
        "stock_id": uuid4(),
        "model_run_id": uuid4(),
        "language": "de",
        "created_at": datetime.now(UTC),
        "one_liner": "kurz aber valide",
        "ranking_interpretation": "x" * 200,
        "sweet_spot": False,
        "sweet_spot_explanation": None,
        "contradictions": [],
        "key_strengths": ["Stabilität"],
        "key_risks": ["FX"],
        "confidence": "medium",
        "model_version": "claude-sonnet-4-6@20260101",
    }
    payload.update(overrides)
    return payload


class TestResearchMemoEntity:
    def test_valid_construct(self) -> None:
        memo = ResearchMemo(**_valid_entity_payload())
        assert memo.language == "de"

    def test_language_default_is_de(self) -> None:
        payload = _valid_entity_payload()
        del payload["language"]
        memo = ResearchMemo(**payload)
        assert memo.language == "de"

    def test_language_accepts_en(self) -> None:
        memo = ResearchMemo(**_valid_entity_payload(language="en"))
        assert memo.language == "en"

    def test_is_frozen(self) -> None:
        """Pydantic v2 frozen erzwingt Immutability via ValidationError beim setattr."""
        memo = ResearchMemo(**_valid_entity_payload())
        with pytest.raises(ValidationError):
            memo.one_liner = "neuer text"

    def test_entity_accepts_short_one_liner_schema_would_reject(self) -> None:
        """Constraint-Asymmetrie zum Schema: Entity erlaubt kurze Strings,
        die das LLM-Schema zurückweisen würde. Bewusst (Spec §3.3)."""
        memo = ResearchMemo(**_valid_entity_payload(one_liner="kurz"))
        assert memo.one_liner == "kurz"

    def test_one_liner_max_length_still_enforced(self) -> None:
        with pytest.raises(ValidationError):
            ResearchMemo(**_valid_entity_payload(one_liner="x" * 151))

    def test_ranking_interpretation_accepts_1000_chars(self) -> None:
        # Schema (LLM-Output) erlaubt bis 1000 Zeichen (commit cabef60,
        # empirisch gegen Sonnet-4-6 kalibriert). Entity muss mindestens
        # gleich permissiv sein, sonst crasht generate_memo Schritt 6 mit
        # ValidationError fuer reale LLM-Outputs zwischen 601-1000 chars.
        memo = ResearchMemo(**_valid_entity_payload(ranking_interpretation="x" * 1000))
        assert len(memo.ranking_interpretation) == 1000

    def test_ranking_interpretation_max_length_1001_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ResearchMemo(**_valid_entity_payload(ranking_interpretation="x" * 1001))


class TestResearchMemoIsError:
    """is_error-Feld: persistierte Markierung statt Router-String-Match (Issue #67)."""

    def test_default_is_error_is_false(self) -> None:
        memo = ResearchMemo(**_valid_entity_payload())
        assert memo.is_error is False

    def test_explicit_is_error_true(self) -> None:
        memo = ResearchMemo(**_valid_entity_payload(is_error=True))
        assert memo.is_error is True
