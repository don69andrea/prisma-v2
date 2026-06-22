"""TechnicalAnalystAgent — interprets engine sub_scores into a TechnicalView.

§0 Iron Rule: The LLM interprets numbers, it NEVER invents them.
All numeric values in the output MUST originate from the sub_scores input.

Pattern: copy of SteuerAgent — constructor injection, json.loads, Pydantic validate,
deterministic fallback on any Exception.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.domain.schemas.agent_schemas import TechnicalView
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MAX_TOKENS = 512


class TechnicalAnalystAgent:
    """Interprets Signal Engine sub_scores into a structured TechnicalView.

    Constructor-injected LLMClient + PromptTemplateLoader (AGENTS.md pattern).
    Uses Haiku model — fast, cheap, interprets numbers only.
    Falls back to a deterministic view on any Exception (no 500s).
    """

    _MODEL = "claude-haiku-4-5-20251001"

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
    ) -> None:
        self._llm = llm_client
        self._prompts = prompt_loader

    async def analyze(self, coin: str, sub_scores: dict[str, Any]) -> TechnicalView:
        """Interpret engine sub_scores and return a validated TechnicalView.

        Args:
            coin: Asset identifier (e.g. "BTC").
            sub_scores: Dict of normalized indicator values from Signal Engine.

        Returns:
            TechnicalView — always, even on LLM failure (deterministic fallback).
        """
        system_prompt = self._prompts.render(
            "technical_analyst.de.md.j2",
            {
                "coin": coin,
                "sub_scores": sub_scores,
            },
        )
        user_prompt = f"Erstelle eine TechnicalView-Einschätzung für {coin} basierend auf den sub_scores im System-Prompt."

        try:
            response = await self._llm.messages_create(
                model=self._MODEL,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=_MAX_TOKENS,
                feature="technical_analyst",
                system=system_prompt,
            )
            raw_text: str = response.content[0].text
            data = json.loads(raw_text)
            data["coin"] = coin  # enforce coin from caller, not LLM
            return TechnicalView.model_validate(data)
        except Exception as exc:
            _logger.error("TechnicalAnalystAgent LLM/validation failed: %s", exc)
            return self._fallback(coin, sub_scores)

    @staticmethod
    def _fallback(coin: str, sub_scores: dict[str, Any]) -> TechnicalView:
        """Deterministic fallback — numbers derived from sub_scores, confidence lowered."""
        # Determine stance from available scores (no LLM invention)
        rsi = sub_scores.get("rsi", 0.5)
        momentum = sub_scores.get("momentum", 0.5)
        avg = (rsi + momentum) / 2.0

        from typing import Literal

        stance_val: Literal["BULLISH", "NEUTRAL", "BEARISH"]
        if avg > 0.6:
            stance_val = "BULLISH"
        elif avg < 0.4:
            stance_val = "BEARISH"
        else:
            stance_val = "NEUTRAL"

        return TechnicalView(
            coin=coin,
            stance=stance_val,
            consensus="1/3",
            key_signals=[
                f"RSI={rsi:.4f} (engine value)",
                "Fallback: LLM-Analyse nicht verfügbar",
            ],
            confidence=0.4,  # lowered — fallback path
            reasoning=(
                f"Fallback-Analyse für {coin}. "
                f"RSI={rsi:.4f}, Momentum={momentum:.4f} (aus Engine). "
                "LLM-Interpretation nicht verfügbar — deterministische Einschätzung."
            ),
        )
