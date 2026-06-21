"""OnChainAnalystAgent — interprets on-chain tool data into an OnChainView.

§0 Iron Rule: The LLM interprets tool data, it NEVER invents numbers.
All numeric values in the output MUST originate from tool data.

Pattern: copy of SteuerAgent — constructor injection, json.loads, Pydantic validate,
deterministic fallback on any Exception.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from backend.domain.schemas.agent_schemas import OnChainView
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MAX_TOKENS = 512


def _get_mvrv_z(coin: str) -> dict[str, Any]:
    """Tool stub: returns MVRV-Z score for the given coin.

    V4-4 will replace with real API call to Glassnode / on-chain provider.
    """
    # Stub data — returns normalized 0..1 values
    return {
        "coin": coin,
        "mvrv_z": 0.45,
        "interpretation": "below average valuation",
    }


def _get_nvt_signal(coin: str) -> dict[str, Any]:
    """Tool stub: returns NVT signal (Network Value to Transactions).

    V4-4 will replace with real on-chain data.
    """
    return {
        "coin": coin,
        "nvt_signal": 0.35,
        "trend_30d": "stable",
    }


def _get_active_addresses(coin: str) -> dict[str, Any]:
    """Tool stub: returns normalized active address growth metric.

    V4-4 will replace with real on-chain data.
    """
    return {
        "coin": coin,
        "active_addresses_norm": 0.62,
        "growth_7d": 0.05,
    }


class OnChainAnalystAgent:
    """Interprets on-chain tool data into a structured OnChainView.

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

    async def analyze(self, coin: str) -> OnChainView:
        """Fetch on-chain tool data and return a validated OnChainView.

        Args:
            coin: Asset identifier (e.g. "BTC").

        Returns:
            OnChainView — always, even on LLM failure (deterministic fallback).
        """
        # Collect tool data (stubs — V4-4 replaces with real feeds)
        tool_data = {
            "mvrv_z": _get_mvrv_z(coin),
            "nvt_signal": _get_nvt_signal(coin),
            "active_addresses": _get_active_addresses(coin),
        }

        system_prompt = self._prompts.render(
            "onchain_analyst.de.md.j2",
            {
                "coin": coin,
                "tool_data": tool_data,
            },
        )
        user_prompt = f"Erstelle eine OnChainView-Einschätzung für {coin} basierend auf den Tool-Daten im System-Prompt."

        try:
            response = await self._llm.messages_create(
                model=self._MODEL,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=_MAX_TOKENS,
                feature="onchain_analyst",
                system=system_prompt,
            )
            raw_text: str = response.content[0].text
            data = json.loads(raw_text)
            data["coin"] = coin  # enforce coin from caller
            return OnChainView.model_validate(data)
        except Exception as exc:
            _logger.error("OnChainAnalystAgent LLM/validation failed: %s", exc)
            return self._fallback(coin, tool_data)

    @staticmethod
    def _fallback(coin: str, tool_data: dict[str, Any]) -> OnChainView:
        """Deterministic fallback — numbers derived from tool data, confidence lowered."""
        mvrv = tool_data.get("mvrv_z", {}).get("mvrv_z", 0.5)
        nvt = tool_data.get("nvt_signal", {}).get("nvt_signal", 0.5)
        addr = tool_data.get("active_addresses", {}).get("active_addresses_norm", 0.5)

        # Valuation from MVRV-Z
        if mvrv < 0.3:
            valuation = "CHEAP"
        elif mvrv > 0.7:
            valuation = "EXPENSIVE"
        else:
            valuation = "FAIR"

        # Network health from active addresses + NVT
        health_score = (addr + (1.0 - nvt)) / 2.0
        if health_score > 0.6:
            network_health = "STRONG"
        elif health_score < 0.4:
            network_health = "WEAK"
        else:
            network_health = "NEUTRAL"

        return OnChainView(
            coin=coin,
            valuation=valuation,
            network_health=network_health,
            confidence=0.4,  # lowered — fallback path
            reasoning=(
                f"Fallback-Analyse für {coin}. "
                f"MVRV-Z={mvrv:.4f}, NVT={nvt:.4f}, ActiveAddr={addr:.4f} (aus Tools). "
                "LLM-Interpretation nicht verfügbar — deterministische Einschätzung."
            ),
        )
