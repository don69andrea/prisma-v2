"""RED test stub — SentimentLLMOutput schema must exist with exactly two fields (REQ-4-06).

Status: RED until backend/domain/schemas/agent_schemas.py adds SentimentLLMOutput
(plan 04-01).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSentimentLLMOutput:
    """REQ-4-06: SentimentLLMOutput(news_surprise:bool, reasoning:str) validates correctly.

    §0 Iron Rule: LLM produces ONLY news_surprise + reasoning.
    score, veto, regime are computed deterministically in Python — never by LLM.
    """

    def test_sentiment_llm_output_importable(self) -> None:
        """SentimentLLMOutput must be importable from agent_schemas."""
        from backend.domain.schemas.agent_schemas import SentimentLLMOutput  # noqa: F401

        assert SentimentLLMOutput is not None

    def test_valid_news_surprise_true(self) -> None:
        """news_surprise=True, reasoning=str — must validate without error."""
        from backend.domain.schemas.agent_schemas import SentimentLLMOutput

        output = SentimentLLMOutput(
            news_surprise=True,
            reasoning="BTC ETF approved — significant bullish news event detected.",
        )
        assert output.news_surprise is True
        assert isinstance(output.reasoning, str)

    def test_valid_news_surprise_false(self) -> None:
        """news_surprise=False validates without error."""
        from backend.domain.schemas.agent_schemas import SentimentLLMOutput

        output = SentimentLLMOutput(
            news_surprise=False,
            reasoning="No significant new events in the retrieved chunks.",
        )
        assert output.news_surprise is False

    def test_non_bool_news_surprise_rejected(self) -> None:
        """news_surprise must be strict bool — a string '\"true\"' must be rejected."""
        from pydantic import ValidationError

        from backend.domain.schemas.agent_schemas import SentimentLLMOutput

        with pytest.raises(ValidationError):
            SentimentLLMOutput(
                news_surprise="yes",  # type: ignore[arg-type]
                reasoning="Some reasoning text.",
            )

    def test_integer_news_surprise_rejected(self) -> None:
        """news_surprise=1 (int truthy) must be rejected — strict bool required."""
        from pydantic import ValidationError

        from backend.domain.schemas.agent_schemas import SentimentLLMOutput

        with pytest.raises(ValidationError):
            SentimentLLMOutput(
                news_surprise=1,  # type: ignore[arg-type]
                reasoning="Some reasoning text.",
            )

    def test_exactly_two_fields(self) -> None:
        """SentimentLLMOutput must have exactly two fields: news_surprise and reasoning.

        This enforces the §0 Iron Rule — no score, veto, regime, or coin fields
        may leak into the LLM output schema.
        """
        from backend.domain.schemas.agent_schemas import SentimentLLMOutput

        fields = set(SentimentLLMOutput.model_fields.keys())
        assert fields == {"news_surprise", "reasoning"}, (
            f"SentimentLLMOutput must have exactly {{news_surprise, reasoning}}, got {fields}"
        )

    def test_missing_reasoning_raises(self) -> None:
        """reasoning is required — omitting it must raise ValidationError."""
        from pydantic import ValidationError

        from backend.domain.schemas.agent_schemas import SentimentLLMOutput

        with pytest.raises(ValidationError):
            SentimentLLMOutput(news_surprise=True)  # type: ignore[call-arg]
