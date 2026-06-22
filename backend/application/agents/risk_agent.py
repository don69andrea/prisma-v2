"""RiskAgent — veto/cap gate for position sizing via Claude Tool-Use API.

§0 Iron Rule: LLM interprets numbers, never invents them.
Portfolio exposure MUST come from the injected Store (D-06 test 2: State-from-Tool).
The LLM NEVER hallucinate exposure values.

D-06 test 7 (No-Shorting): Python post-LLM enforcement:
  - if engine_signal.action == "SELL": force max_size = 0.0
  - clamp max_size to [0.0, 1.5] (RiskVerdict schema already enforces upper bound)

Pattern: mirrors UniverseSuggestionService tool-use pattern:
  - tools=[{"name": ..., "description": ..., "input_schema": RiskVerdict.model_json_schema()}]
  - tool_choice={"type": "tool", "name": "submit_risk_verdict"}
  - Extract block where block.type == "tool_use"
  - RiskVerdict.model_validate(block.input)
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from pydantic import ValidationError

from backend.domain.schemas.agent_schemas import RiskVerdict
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024

_TOOL_NAME = "submit_risk_verdict"
_TOOL_DESCRIPTION = (
    "Submit the risk assessment verdict for the proposed position. "
    "Include any risk breaches and the maximum allowed position size."
)

# Conservative fallback values used when LLM is unavailable
_FALLBACK_MAX_SIZE = 0.0
_FALLBACK_REASONING = (
    "Konservativer Fallback: LLM-Risikobewertung nicht verfügbar. "
    "Position auf 0 gesetzt — manuelle Prüfung erforderlich."
)


class ExposureStore(Protocol):
    """Protocol for portfolio exposure Store/repository.

    D-06 test 2: RiskAgent reads exposure from THIS store, never from LLM memory.
    """

    async def get_exposure(self, coin: str) -> float:
        """Return current portfolio exposure for the given coin (0.0 to 1.5)."""
        ...


class RiskAgent:
    """Issues veto/cap decisions on position sizing via Tool-Use API.

    D-06 test 2 (State-from-Tool): Portfolio exposure is read from the injected
    ExposureStore BEFORE the LLM call. The real exposure value is passed into
    the prompt context — the LLM never invents exposure from memory.

    D-06 test 7 (No-Shorting): Python post-LLM enforcement clamps max_size:
      - SELL signal → max_size = 0.0 (Python override, not LLM decision)
      - max_size always clamped to [0.0, 1.5]

    Constructor-injected LLMClient, PromptTemplateLoader, ExposureStore.
    Uses Sonnet model — safety-critical assessment requires research-grade model.
    Falls back to conservative RiskVerdict on any Exception (no 500s, fail safe).
    """

    _MODEL = _MODEL

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
        exposure_store: ExposureStore,
    ) -> None:
        self._llm = llm_client
        self._prompts = prompt_loader
        self._exposure_store = exposure_store

    async def assess(
        self,
        coin: str,
        engine_signal: Any,
    ) -> RiskVerdict:
        """Assess risk and issue a veto/cap verdict.

        Step 1: Read current portfolio exposure from Store (D-06 test 2).
        Step 2: Inject real exposure into prompt context (not from LLM memory).
        Step 3: Call LLM with forced Tool-Use for structured RiskVerdict.
        Step 4: Apply post-LLM invariants (D-06 test 7 No-Shorting).

        Args:
            coin: Asset identifier (e.g. "BTC").
            engine_signal: SignalVector from Signal Engine (action, size_factor, confidence).

        Returns:
            RiskVerdict — always, even on LLM failure (conservative fallback).
        """
        # D-06 test 2: Read exposure from Store FIRST — before any LLM call
        try:
            current_exposure = await self._exposure_store.get_exposure(coin)
        except Exception as exc:
            _logger.warning("ExposureStore unavailable for %s: %s — using 0.0", coin, exc)
            current_exposure = 0.0

        system_prompt = self._prompts.render(
            "risk_agent.de.md.j2",
            {
                "coin": coin,
                "engine_signal": engine_signal,
                "current_exposure": current_exposure,  # real Store value, not LLM invention
            },
        )

        tools = [
            {
                "name": _TOOL_NAME,
                "description": _TOOL_DESCRIPTION,
                "input_schema": RiskVerdict.model_json_schema(),
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
                        "content": (
                            f"Bewerte das Risiko für {coin} mit aktueller Exposition "
                            f"{current_exposure:.4f} und Signal {getattr(engine_signal, 'action', 'HOLD')}."
                        ),
                    }
                ],
                tools=tools,
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                max_tokens=_MAX_TOKENS,
                feature="risk_agent",
            )
            verdict = self._extract_verdict(response)
        except Exception as exc:
            _logger.error("RiskAgent LLM/validation failed: %s", exc)
            verdict = self._fallback(coin, engine_signal)

        # D-06 test 7: Post-LLM invariant enforcement (Python, not LLM)
        verdict = self._enforce_no_shorting(verdict, engine_signal)
        return verdict

    @staticmethod
    def _extract_verdict(response: object) -> RiskVerdict:
        """Extract RiskVerdict from tool_use block in Anthropic response."""
        content = getattr(response, "content", [])
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return RiskVerdict.model_validate(block.input)
                except ValidationError as exc:
                    _logger.warning("RiskVerdict schema violation: %s", exc)
                    raise
        raise ValueError("Keine tool_use-Antwort vom LLM erhalten (RiskAgent).")

    @staticmethod
    def _enforce_no_shorting(verdict: RiskVerdict, engine_signal: Any) -> RiskVerdict:
        """D-06 test 7: Enforce no-shorting invariant post-LLM.

        If engine_signal.action == "SELL": force max_size = 0.0.
        Always clamp max_size to [0.0, 1.5].
        Returns a new RiskVerdict with corrected max_size (immutable update).
        """
        action = getattr(engine_signal, "action", "HOLD")
        max_size = verdict.max_size

        # SELL → no position allowed (cash out, no short)
        if action == "SELL":
            max_size = 0.0

        # Clamp to valid range [0.0, 1.5]
        max_size = max(0.0, min(1.5, max_size))

        if max_size == verdict.max_size:
            return verdict

        # Return updated verdict with corrected max_size
        return RiskVerdict(
            approve=verdict.approve,
            max_size=max_size,
            breaches=verdict.breaches,
            reasoning=verdict.reasoning,
        )

    @staticmethod
    def _fallback(coin: str, engine_signal: Any) -> RiskVerdict:
        """Conservative deterministic fallback when LLM is unavailable."""
        return RiskVerdict(
            approve=False,
            max_size=0.0,
            breaches=[f"LLM-Risikobewertung nicht verfügbar für {coin}"],
            reasoning=_FALLBACK_REASONING,
        )
