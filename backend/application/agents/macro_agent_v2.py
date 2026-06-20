"""MacroAgent V2 — LLM Tool-Use Loop statt rule-based if/elif."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from backend.domain.data.macro_profiles import DOMESTIC_FOCUS as _DOMESTIC_FOCUS
from backend.domain.data.macro_profiles import EXPORT_HEAVY as _EXPORT_HEAVY
from backend.domain.schemas.multiagent_schemas import MacroToolReport

_logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 600
_MAX_ITERATIONS = 5

_MACRO_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_snb_rate",
        "description": "Gibt den aktuellen SNB-Leitzins in % zurück.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_chf_eur",
        "description": "Gibt den aktuellen CHF/EUR-Kurs zurück (1 CHF in EUR).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_inflation_ch",
        "description": "Gibt die aktuelle Schweizer Inflationsrate (YoY) in % zurück.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_ticker_export_profile",
        "description": "Gibt zurück ob ein Ticker exportlastig, inlandsfokussiert oder neutral ist.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
]

_SYSTEM = """Du bist ein präziser Makro-Analyst für Schweizer Aktien.
Nutze die Tools um aktuelle Makrodaten abzurufen.
Berechne dann einen Makro-Score (0-100) für den angegebenen Ticker.

Score-Leitfaden:
- 50 = Baseline
- SNB-Leitzins 0%: +20, bis 0.5%: +15, bis 1%: +5, bis 1.5%: -10, >1.5%: -20
- CHF stark (>0.95/EUR) + Exporteur: -15; CHF stark + Inlandstitel: +5
- CHF schwach (<0.91/EUR) + Exporteur: +10
- Inflation 0-2%: +10; Inflation >3%: -10; Deflation: -5

Antworte NUR mit JSON (kein Markdown):
{"score": float, "chf_impact": "POSITIV|NEUTRAL|NEGATIV", "reasoning": "max 2 Sätze"}"""


class MacroAgentV2:
    def __init__(self, macro_service: Any, llm_client: Any) -> None:
        self._macro = macro_service
        self._llm = llm_client

    async def get_macro_report(self, ticker: str, sector: str | None = None) -> MacroToolReport:
        """Berechnet Makro-Score via Claude Tool-Use Loop."""
        try:
            ctx = await self._macro.get_context()
        except Exception as exc:
            _logger.error("MacroService.get_context() fehlgeschlagen: %s", exc)
            return self._fallback(ticker, 0.25, 0.93)

        _tool_data: dict[str, Any] = {
            "get_snb_rate": {"leitzins": ctx.leitzins},
            "get_chf_eur": {"chf_eur": ctx.chf_eur},
            "get_inflation_ch": {"inflation_ch": getattr(ctx, "inflation_ch", 0.8)},
            "get_ticker_export_profile": {
                "ticker": ticker.upper(),
                "profile": (
                    "exportlastig"
                    if ticker.upper() in _EXPORT_HEAVY
                    else "inlandsfokussiert"
                    if ticker.upper() in _DOMESTIC_FOCUS
                    else "neutral"
                ),
                "sector": sector or "unbekannt",
            },
        }

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"Analysiere den Makro-Score für {ticker.upper()}"
                    + (f" (Sektor: {sector})" if sector else "")
                    + ". Rufe alle relevanten Tools auf und berechne den Score."
                ),
            }
        ]

        try:
            for _ in range(_MAX_ITERATIONS):
                response = await self._llm.messages_create(
                    model=_MODEL,
                    system=_SYSTEM,
                    messages=messages,
                    tools=_MACRO_TOOLS,
                    max_tokens=_MAX_TOKENS,
                    feature="macro_agent_v2",
                )

                if response.stop_reason == "end_turn":
                    text_block = next(
                        (b for b in response.content if getattr(b, "type", None) == "text"), None
                    )
                    if text_block:
                        return self._parse(ticker, text_block.text, ctx.leitzins, ctx.chf_eur)
                    break

                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = _tool_data.get(block.name, {"error": "Tool nicht gefunden"})
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            _logger.error("MacroAgentV2 LLM-Loop fehlgeschlagen: %s", exc)

        return self._fallback(ticker, ctx.leitzins, ctx.chf_eur)

    def _parse(self, ticker: str, text: str, leitzins: float, chf_eur: float) -> MacroToolReport:
        try:
            data = json.loads(text.strip())
            return MacroToolReport(
                ticker=ticker.upper(),
                score=float(data["score"]),
                leitzins=leitzins,
                chf_eur=chf_eur,
                climate="tool-use",
                chf_impact=data.get("chf_impact", "NEUTRAL"),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValidationError, KeyError) as exc:
            _logger.warning("MacroAgentV2 parse-Fehler: %s", exc)
            return self._fallback(ticker, leitzins, chf_eur)

    @staticmethod
    def _fallback(ticker: str, leitzins: float, chf_eur: float) -> MacroToolReport:
        score = 50.0
        if leitzins <= 0.5:
            score += 15
        elif leitzins > 1.5:
            score -= 20
        return MacroToolReport(
            ticker=ticker.upper(),
            score=round(score, 2),
            leitzins=leitzins,
            chf_eur=chf_eur,
            climate="fallback",
            chf_impact="NEUTRAL",
            reasoning="Makro-Analyse nicht verfügbar — Fallback verwendet.",
        )
