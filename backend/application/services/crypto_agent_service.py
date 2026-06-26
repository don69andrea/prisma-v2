"""CryptoAgentService — Claude analysiert Krypto-Signale + erkannte Patterns.

`analyze_brief()` (Cron, nicht-streaming) läuft über den LLMClient-Wrapper —
Budget-Cap-Check + Cost-Audit-Log, projektweite Pflicht für Application-Layer
LLM-Calls (siehe AGENTS.md/CLAUDE.md).

`stream_analysis()` (on-demand SSE) nutzt seit FIX-01 `self._llm.raw_client` —
kein direktes `anthropic.AsyncAnthropic()` mehr in der Application-Layer.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.infrastructure.llm.client import LLMClient

_logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """Du bist ein präziser Krypto-Analyst bei einer Schweizer Finanzplattform (PRISMA).
Deine Aufgabe: Erkläre in 2 Sätzen auf Deutsch, WARUM dieser Titel seinen aktuellen Score hat.
- Nenne die 1-2 stärksten treibenden Faktoren aus den Score-Komponenten
- Erkläre den Zusammenhang — nicht nur die Zahlen wiederholen
- Kein Hype, keine Empfehlungen ("kaufen"/"verkaufen")
- Sachlich, klar, unter 60 Wörtern
- Schreibe im Präsens"""


def _build_prompt(ticker: str, data: dict[str, Any], patterns: list[str]) -> str:
    pattern_str = ", ".join(patterns[:5]) if patterns else "Keine"
    score = data.get("score") or 0.0
    components: dict[str, float] = data.get("score_components") or {}
    components_str = (
        ", ".join(f"{k} {v:.0f}" for k, v in components.items())
        if components
        else "nicht verfügbar"
    )
    return (
        f"Erkläre warum {ticker} diesen Score hat:\n"
        f"- Signal: {data.get('signal', '?')} (Score: {score:.1f}/100)\n"
        f"- Score-Komponenten: {components_str}\n"
        f"- RSI: {data.get('rsi_14', '?')}\n"
        f"- MACD-Richtung: {data.get('macd_signal', '?')}\n"
        f"- Fear & Greed Index: {data.get('fear_greed_value', '?')}\n"
        f"- Erkannte Patterns: {pattern_str}\n"
        f"Schreibe 2 Sätze auf Deutsch, die den Grund für den Score erklären."
    )


class CryptoAgentService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def analyze_brief(self, ticker: str, signal_data: Any, patterns: list[str]) -> str:
        """2-Satz DE-Kurzanalyse, nicht-streaming (für den täglichen Cron-Snapshot)."""
        data = {
            "signal": getattr(signal_data, "signal", None),
            "score": getattr(signal_data, "score", None),
            "score_components": getattr(signal_data, "score_components", None),
            "rsi_14": getattr(signal_data, "rsi_14", None),
            "macd_signal": getattr(signal_data, "macd_signal", None),
            "fear_greed_value": getattr(signal_data, "fear_greed_value", None),
        }
        try:
            response = await self._llm.messages_create(
                model=_MODEL,
                max_tokens=120,
                feature="crypto_agent_brief",
                system=[
                    {"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": _build_prompt(ticker, data, patterns)}],
            )
            return str(response.content[0].text).strip()
        except Exception as exc:
            _logger.warning("CryptoAgentService.analyze_brief fehlgeschlagen (%s): %s", ticker, exc)
            return ""

    async def stream_analysis(
        self, ticker: str, signal_data: dict[str, Any], patterns: list[str]
    ) -> AsyncIterator[str]:
        """Streamt die Analyse als rohe Text-Tokens (für SSE-Endpoint, on-demand)."""
        # FIX-01: raw_client nutzt den prozess-weiten Connection-Pool (Singleton) aus get_anthropic_client().
        # Kein eigenes anthropic.AsyncAnthropic() mehr — alle Streaming-Calls laufen über LLMClient.raw_client.
        try:
            client = self._llm.raw_client
            prompt = _build_prompt(ticker, signal_data, patterns)
            async with client.messages.stream(
                model=_MODEL,
                max_tokens=150,
                system=[
                    {"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            _logger.error("CryptoAgentService.stream_analysis fehlgeschlagen (%s): %s", ticker, exc)
            yield "Analyse aktuell nicht verfügbar."
