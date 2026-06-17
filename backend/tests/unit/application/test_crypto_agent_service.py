"""Unit-Tests für CryptoAgentService — LLM-Kurzanalyse für Krypto-Signale.

analyze_brief() läuft über LLMClient (Cap-Check + Cost-Tracking, Fixture-Mode
— nie gegen die Live-API in CI, siehe CLAUDE.md). stream_analysis() nutzt seit
FIX-01 self._llm.raw_client statt eigenem AsyncAnthropic().
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.application.services.crypto_agent_service import CryptoAgentService
from backend.tests.fixtures.llm.fixture_llm_client import FixtureLLMClient

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "llm" / "crypto"


def _fake_signal(**overrides: Any) -> SimpleNamespace:
    defaults = dict(
        signal="BUY",
        score=78.5,
        rsi_14=28.0,
        macd_signal="bullish",
        fear_greed_value=22,
    )
    return SimpleNamespace(**{**defaults, **overrides})


class TestAnalyzeBrief:
    async def test_returns_text_from_fixture_response(self) -> None:
        fixture_client = FixtureLLMClient([FIXTURES / "btc_brief_analysis.json"])
        svc = CryptoAgentService(llm_client=fixture_client.llm)

        result = await svc.analyze_brief("BTC-CHF", _fake_signal(), ["GOLDEN_CROSS"])

        assert "Bitcoin" in result
        assert result != ""

    async def test_calls_llm_with_haiku_model(self) -> None:
        fixture_client = FixtureLLMClient([FIXTURES / "btc_brief_analysis.json"])
        svc = CryptoAgentService(llm_client=fixture_client.llm)

        await svc.analyze_brief("BTC-CHF", _fake_signal(), ["GOLDEN_CROSS"])

        call = fixture_client.calls[0]
        assert call["model"] == "claude-haiku-4-5-20251001"

    async def test_system_prompt_uses_ephemeral_cache_control(self) -> None:
        fixture_client = FixtureLLMClient([FIXTURES / "btc_brief_analysis.json"])
        svc = CryptoAgentService(llm_client=fixture_client.llm)

        await svc.analyze_brief("BTC-CHF", _fake_signal(), [])

        call = fixture_client.calls[0]
        assert call["system"][0]["cache_control"] == {"type": "ephemeral"}

    async def test_llm_failure_returns_empty_string(self) -> None:
        broken_llm = MagicMock()

        async def _raise(**kwargs):
            raise RuntimeError("LLM down")

        broken_llm.messages_create = _raise
        svc = CryptoAgentService(llm_client=broken_llm)

        result = await svc.analyze_brief("BTC-CHF", _fake_signal(), [])
        assert result == ""


class TestStreamAnalysis:
    async def test_stream_analysis_on_error_yields_error_message(self) -> None:
        """FIX-01: stream_analysis nutzt raw_client — bei Fehler wird Error-Message geliefert.
        Früher: Eigener api_key-Guard → 'API Key fehlt'.
        Jetzt: Exception vom SDK → 'Analyse aktuell nicht verfügbar.'"""
        mock_llm = MagicMock()
        mock_llm.raw_client.messages.stream.side_effect = Exception("auth error")

        svc = CryptoAgentService(llm_client=mock_llm)
        chunks = [chunk async for chunk in svc.stream_analysis("BTC-CHF", {}, [])]

        assert len(chunks) == 1
        assert "nicht verfügbar" in chunks[0]
