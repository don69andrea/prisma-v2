"""Unit-Tests für SteuerAgent."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.agents.steuer_agent import SteuerAgent
from backend.domain.schemas.steuer_schema import PFLICHT_DISCLAIMER

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 8, 7, 0, tzinfo=UTC)

_VALID_LLM_OUTPUT = {
    "ticker": "NESN",
    "anlegerprofil": "vorsorge_3a",
    "halteperiode_jahre": 30,
    "steuerarten": ["Verrechnungssteuer (35%)", "Vermögenssteuer"],
    "pflichten": [
        "VST-Rückerstattung via Formular 103",
        "Kapital bei Bezug pauschal besteuert",
    ],
    "hinweise": ["3a-Erträge laufend steuerbefreit"],
    "quellen": ["ESTV VST", "BVV2 Art. 53"],
    "disclaimer": PFLICHT_DISCLAIMER,
    "generated_at": _NOW.isoformat(),
    "model_version": "claude-sonnet-4-6",
}


def _build_agent(llm_response: str | None = None) -> SteuerAgent:
    mock_retrieval = AsyncMock()
    mock_retrieval.retrieve.return_value = []

    mock_llm = AsyncMock()
    if llm_response is not None:
        mock_content = MagicMock()
        mock_content.text = llm_response
        mock_llm.messages_create.return_value = MagicMock(content=[mock_content])

    mock_prompts = MagicMock()
    mock_prompts.render.return_value = "rendered prompt"

    return SteuerAgent(
        llm_client=mock_llm,
        retrieval_service=mock_retrieval,
        prompt_loader=mock_prompts,
    )


class TestSteuerAgent:
    async def test_valid_output_returns_einschaetzung(self) -> None:
        agent = _build_agent(json.dumps(_VALID_LLM_OUTPUT))
        result = await agent.einschaetzen("NESN", "vorsorge_3a", 30)
        assert result.ticker == "NESN"
        assert result.anlegerprofil == "vorsorge_3a"
        assert result.halteperiode_jahre == 30
        assert len(result.steuerarten) >= 1
        assert len(result.pflichten) >= 1

    async def test_disclaimer_always_present(self) -> None:
        modified = {**_VALID_LLM_OUTPUT, "disclaimer": "No disclaimer here"}
        agent = _build_agent(json.dumps(modified))
        result = await agent.einschaetzen("NESN", "vorsorge_3a", 30)
        assert result.disclaimer == PFLICHT_DISCLAIMER

    async def test_disclaimer_not_empty_in_fallback(self) -> None:
        # LLM returns invalid JSON → fallback
        agent = _build_agent("INVALID JSON {{{")
        result = await agent.einschaetzen("NESN", "vorsorge_3a", 30)
        assert result.disclaimer == PFLICHT_DISCLAIMER
        assert result.model_version == "fallback"

    async def test_ticker_uppercased(self) -> None:
        modified = {**_VALID_LLM_OUTPUT, "ticker": "nesn"}
        agent = _build_agent(json.dumps(modified))
        result = await agent.einschaetzen("nesn", "vorsorge_3a", 30)
        assert result.ticker == "NESN"

    async def test_rag_retrieval_failure_is_tolerated(self) -> None:
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve.side_effect = RuntimeError("DB offline")
        mock_llm = AsyncMock()
        mock_content = MagicMock()
        mock_content.text = json.dumps(_VALID_LLM_OUTPUT)
        mock_llm.messages_create.return_value = MagicMock(content=[mock_content])
        mock_prompts = MagicMock()
        mock_prompts.render.return_value = "prompt"
        agent = SteuerAgent(
            llm_client=mock_llm,
            retrieval_service=mock_retrieval,
            prompt_loader=mock_prompts,
        )
        result = await agent.einschaetzen("NESN", "vorsorge_3a", 30)
        assert result.ticker == "NESN"

    async def test_pydantic_validation_failure_triggers_fallback(self) -> None:
        # Missing required field 'steuerarten'
        incomplete = {
            "ticker": "NESN",
            "anlegerprofil": "vorsorge_3a",
            "halteperiode_jahre": 30,
            # steuerarten missing → Pydantic error → fallback
            "pflichten": ["p1"],
            "disclaimer": PFLICHT_DISCLAIMER,
            "generated_at": _NOW.isoformat(),
            "model_version": "test",
        }
        agent = _build_agent(json.dumps(incomplete))
        result = await agent.einschaetzen("NESN", "vorsorge_3a", 30)
        assert result.disclaimer == PFLICHT_DISCLAIMER

    async def test_privatperson_profile_accepted(self) -> None:
        modified = {**_VALID_LLM_OUTPUT, "anlegerprofil": "privatperson"}
        agent = _build_agent(json.dumps(modified))
        result = await agent.einschaetzen("NESN", "privatperson", 10)
        assert result.anlegerprofil == "privatperson"

    async def test_fallback_differentiates_ch_vs_us_ticker(self) -> None:
        # LLM liefert ungültiges JSON → Fallback-Pfad für beide Ticker erzwungen.
        ch_agent = _build_agent("INVALID JSON {{{")
        us_agent = _build_agent("INVALID JSON {{{")

        ch_result = await ch_agent.einschaetzen("NESN", "privatperson", 5)
        us_result = await us_agent.einschaetzen("TSLA", "privatperson", 5)

        assert ch_result.model_version == "fallback"
        assert us_result.model_version == "fallback"

        # CH-Aktien: Verrechnungssteuer + Formular 103 sind korrekt.
        assert any("Verrechnungssteuer" in s for s in ch_result.steuerarten)
        assert any("Formular 103" in p for p in ch_result.pflichten)

        # US-Aktien: KEINE Schweizer Verrechnungssteuer / Formular 103 — andere
        # Steuerarten (US-Quellensteuer / DA-1-Anhang / W8BEN).
        assert not any("Verrechnungssteuer" in s for s in us_result.steuerarten)
        assert not any("Formular 103" in p for p in us_result.pflichten)
        assert any("US-Quellensteuer" in s for s in us_result.steuerarten)
        assert any("DA-1" in p or "W8BEN" in p or "W-8BEN" in p for p in us_result.pflichten)

        # Die beiden Outputs müssen sich materiell unterscheiden.
        assert ch_result.steuerarten != us_result.steuerarten
        assert ch_result.pflichten != us_result.pflichten
