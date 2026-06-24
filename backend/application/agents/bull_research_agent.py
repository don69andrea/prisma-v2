"""BullResearchAgent — deliberately one-sided bullish thesis via Claude Tool-Use API.

§0 Iron Rule: LLM interprets numbers, never invents them.
All numeric values in the output MUST originate from inputs passed by the caller.

Pattern: mirrors UniverseSuggestionService tool-use pattern:
  - tools=[{"name": ..., "description": ..., "input_schema": BullCase.model_json_schema()}]
  - tool_choice={"type": "tool", "name": "submit_bull_case"}
  - Extract block where block.type == "tool_use"
  - BullCase.model_validate(block.input)

Minority Protection: BullCase is ALWAYS built and ALWAYS persisted in audit trail,
even if the Bear/Risk agents disagree. Both sides of the debate are preserved.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from backend.domain.schemas.agent_schemas import BullCase
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024

_TOOL_NAME = "submit_bull_case"
_TOOL_DESCRIPTION = (
    "Submit the one-sided bullish investment thesis for the given coin. "
    "Argue the strongest possible bull case, acknowledging risks honestly."
)


class BullResearchAgent:
    """Produces deliberately one-sided bullish theses via forced Tool-Use API.

    Constructor-injected LLMClient + PromptTemplateLoader (AGENTS.md pattern).
    Uses Sonnet model — research-grade synthesis, not fast Haiku.
    Falls back to a deterministic BullCase on any Exception (no 500s).
    """

    _MODEL = _MODEL

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
    ) -> None:
        self._llm = llm_client
        self._prompts = prompt_loader

    async def build_case(
        self,
        tech: Any,
        onchain: Any,
        senti: Any,
        macro: Any,
        engine_signal: Any,
        coin: str = "BTC",
    ) -> BullCase:
        """Build a one-sided bullish case via Claude Tool-Use API.

        Args:
            tech: TechnicalView from TechnicalAnalystAgent.
            onchain: OnChainView from OnChainAnalystAgent.
            senti: SentimentView from SentimentAnalystAgent.
            macro: MacroRegime from MacroRegimeAgent.
            engine_signal: SignalVector from Signal Engine.
            coin: Asset identifier.

        Returns:
            BullCase — always, even on LLM failure (deterministic fallback).
        """
        system_prompt = self._prompts.render(
            "bull_research.de.md.j2",
            {
                "coin": coin,
                "tech": tech,
                "onchain": onchain,
                "senti": senti,
                "macro": macro,
                "engine_signal": engine_signal,
            },
        )

        tools = [
            {
                "name": _TOOL_NAME,
                "description": _TOOL_DESCRIPTION,
                "input_schema": BullCase.model_json_schema(),
            }
        ]

        try:
            response = await self._llm.messages_create(
                model=_MODEL,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f"Erstelle jetzt die stärkste bullische These für {coin}.",
                    }
                ],
                tools=tools,
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                max_tokens=_MAX_TOKENS,
                feature="bull_research_agent",
            )
            return self._extract_bull_case(response)
        except Exception as exc:
            _logger.error("BullResearchAgent LLM/validation failed: %s", exc)
            return self._fallback(coin, engine_signal)

    @staticmethod
    def _extract_bull_case(response: object) -> BullCase:
        """Extract BullCase from tool_use block in Anthropic response.

        Raises InvalidLLMOutput if no tool_use block found or schema validation fails.
        Falls through to fallback in build_case().
        """
        content = getattr(response, "content", [])
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return BullCase.model_validate(block.input)
                except ValidationError as exc:
                    _logger.warning("BullCase schema violation: %s | input keys: %s", exc, list(block.input.keys()) if isinstance(block.input, dict) else type(block.input))
                    raise
        # No tool_use block found — raise so build_case() uses fallback
        raise ValueError("Keine tool_use-Antwort vom LLM erhalten (BullResearchAgent).")

    @staticmethod
    def _fallback(coin: str, engine_signal: Any) -> BullCase:
        """Deterministic fallback — numbers derived from engine signal only, no LLM."""
        action = getattr(engine_signal, "action", "HOLD")
        confidence = getattr(engine_signal, "confidence", 0.5)

        return BullCase(
            thesis=(
                f"Fallback-Bullcase für {coin}. "
                f"Signal Engine: {action} mit Confidence {confidence:.2f}. "
                "LLM-Synthese nicht verfügbar — deterministischer Fallback."
            ),
            strongest_points=[
                f"Signal Engine signalisiert {action} (Confidence {confidence:.2f})",
                "Fallback: LLM-Analyse nicht verfügbar",
            ],
            risks_acknowledged=[
                "Analyse-Qualität eingeschränkt (LLM-Fallback aktiv)",
                "Manuelle Verifikation empfohlen",
            ],
        )
