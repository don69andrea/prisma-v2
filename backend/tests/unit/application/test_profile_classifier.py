"""Unit-Tests für ProfileClassifier."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.services.profile_classifier import ProfileClassifier
from backend.domain.entities.investor_profile import InvestorProfile

pytestmark = pytest.mark.unit


def _make_llm_mock(response_text: str) -> MagicMock:
    """Erstellt einen LLMClient-Mock, der response_text als content[0].text zurückgibt."""
    content_block = MagicMock()
    content_block.text = response_text
    response = MagicMock()
    response.content = [content_block]

    llm = MagicMock()
    llm.messages_create = AsyncMock(return_value=response)
    return llm


class TestClassifyTurn1:
    @pytest.mark.asyncio
    async def test_tech_profession(self) -> None:
        payload = json.dumps({"financial_knowledge": "medium", "sector_hint": "tech"})
        classifier = ProfileClassifier(llm_client=_make_llm_mock(payload))
        result = await classifier.classify_turn1("Softwareentwickler")
        assert result.financial_knowledge == "medium"
        assert result.sector_hint == "tech"

    @pytest.mark.asyncio
    async def test_finance_profession(self) -> None:
        payload = json.dumps({"financial_knowledge": "high", "sector_hint": "finance"})
        classifier = ProfileClassifier(llm_client=_make_llm_mock(payload))
        result = await classifier.classify_turn1("Bankangestellter")
        assert result.financial_knowledge == "high"

    @pytest.mark.asyncio
    async def test_null_sector_hint(self) -> None:
        payload = json.dumps({"financial_knowledge": "low", "sector_hint": None})
        classifier = ProfileClassifier(llm_client=_make_llm_mock(payload))
        result = await classifier.classify_turn1("Schreiner")
        assert result.sector_hint is None

    @pytest.mark.asyncio
    async def test_llm_called_with_haiku_model(self) -> None:
        payload = json.dumps({"financial_knowledge": "low", "sector_hint": None})
        llm = _make_llm_mock(payload)
        classifier = ProfileClassifier(llm_client=llm)
        await classifier.classify_turn1("Bäcker")
        call_kwargs = llm.messages_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["feature"] == "profile_classification_turn1"


class TestClassifyTurn2:
    def test_altersvorsorge(self) -> None:
        goal, horizon = ProfileClassifier.classify_turn2("Altersvorsorge")
        assert goal == "retirement"
        assert horizon == "long"

    def test_neue_wohnung(self) -> None:
        goal, horizon = ProfileClassifier.classify_turn2("Neue Wohnung")
        assert goal == "housing"
        assert horizon == "short"

    def test_finanzielle_freiheit(self) -> None:
        goal, horizon = ProfileClassifier.classify_turn2("Finanzielle Freiheit")
        assert goal == "freedom"
        assert horizon == "medium"

    def test_unknown_falls_back_to_other(self) -> None:
        goal, horizon = ProfileClassifier.classify_turn2("Irgendwas anderes")
        assert goal == "other"
        assert horizon == "medium"


class TestClassifyTurn3:
    def test_conservative(self) -> None:
        assert ProfileClassifier.classify_turn3("conservative") == "conservative"

    def test_aggressive(self) -> None:
        assert ProfileClassifier.classify_turn3("aggressive") == "aggressive"

    def test_invalid_falls_back_to_moderate(self) -> None:
        assert ProfileClassifier.classify_turn3("unknown_value") == "moderate"


class TestClassifyTurn4:
    def test_extracts_sectors(self) -> None:
        brand_data = {
            "NESN.SW": {"sector": "consumer"},
            "LOGN.SW": {"sector": "tech"},
        }
        sectors, tickers = ProfileClassifier.classify_turn4(["NESN.SW", "LOGN.SW"], brand_data)
        assert set(sectors) == {"consumer", "tech"}
        assert set(tickers) == {"NESN.SW", "LOGN.SW"}

    def test_missing_tickers_skipped(self) -> None:
        brand_data = {"NESN.SW": {"sector": "consumer"}}
        sectors, tickers = ProfileClassifier.classify_turn4(["NESN.SW", "UNKNOWN.SW"], brand_data)
        assert sectors == ["consumer"]
        assert "UNKNOWN.SW" in tickers  # ticker stays, just no sector entry

    def test_empty_input(self) -> None:
        sectors, tickers = ProfileClassifier.classify_turn4([], {})
        assert sectors == []
        assert tickers == []


class TestCalculateConfidence:
    def _profile(self, **kwargs: Any) -> InvestorProfile:
        return InvestorProfile(session_id="s", **kwargs)

    def test_empty_profile_is_zero(self) -> None:
        p = self._profile()
        assert ProfileClassifier.calculate_confidence(p) == 0.0

    def test_profession_adds_to_score(self) -> None:
        p = self._profile(profession="Ingenieur")
        assert ProfileClassifier.calculate_confidence(p) >= 0.2

    def test_non_default_goal_adds_score(self) -> None:
        p = self._profile(investment_goal="retirement")
        assert ProfileClassifier.calculate_confidence(p) >= 0.2

    def test_non_default_risk_adds_score(self) -> None:
        p = self._profile(risk_profile="aggressive")
        assert ProfileClassifier.calculate_confidence(p) >= 0.3

    def test_two_known_tickers_adds_score(self) -> None:
        p = self._profile(known_tickers=["NESN.SW", "ROG.SW"])
        assert ProfileClassifier.calculate_confidence(p) >= 0.2

    def test_full_profile_reaches_high_confidence(self) -> None:
        p = self._profile(
            profession="Banker",
            financial_knowledge="high",
            investment_goal="retirement",
            risk_profile="aggressive",
            known_tickers=["NESN.SW", "ROG.SW", "LOGN.SW"],
            sector_affinity=["pharma"],
        )
        score = ProfileClassifier.calculate_confidence(p)
        assert score >= 0.8

    def test_score_capped_at_1(self) -> None:
        p = self._profile(
            profession="Banker",
            financial_knowledge="high",
            investment_goal="retirement",
            risk_profile="conservative",
            known_tickers=["NESN.SW", "ROG.SW", "NOVN.SW"],
            sector_affinity=["pharma", "tech"],
        )
        assert ProfileClassifier.calculate_confidence(p) <= 1.0
