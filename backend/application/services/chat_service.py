"""Application Service: PRISMA Chat — Claude Tool Use + SSE Streaming.

Tool-Registry-Pattern: Jeder Tool-Handler ist eine eigenständige async-Funktion.
Eine DB-Session wird einmal pro Tool-Call geöffnet und an den Handler übergeben.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist PRISMA Assistant — ein präziser, datengetriebener Finanz-Assistent.
Du hast Zugriff auf das PRISMA-Universum (SMI/SMIM/SPI + US-Aktien) via Tools.
Antworte IMMER auf Basis der Tool-Ergebnisse — nie aus deinem Trainingswissen über aktuelle Preise.
Sprache: Deutsch bevorzugt. Englisch wenn der Nutzer auf Englisch schreibt.
Bei konkreten Kauf-/Verkaufsempfehlungen: füge immer hinzu "Keine Anlageberatung."
Sei präzise und knapp — maximal 3 Absätze pro Antwort."""

_MODEL = "claude-sonnet-4-6"
_TOOL_RESULT_MAX_CHARS = 2000

# Type alias für Tool-Handler: (inputs, session) → JSON-String
ToolHandler = Callable[[dict[str, Any], AsyncSession], Awaitable[str]]

# Registry: Tool-Name → Handler-Funktion
_TOOL_REGISTRY: dict[str, ToolHandler] = {}


def _register(name: str) -> Callable[[ToolHandler], ToolHandler]:
    def decorator(fn: ToolHandler) -> ToolHandler:
        _TOOL_REGISTRY[name] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Tool-Handler (alle importieren Services am Dateianfang, nicht inline)
# ---------------------------------------------------------------------------

from backend.application.services.macro_service import MacroService  # noqa: E402
from backend.application.services.swiss_market_service import SwissMarketService  # noqa: E402
from backend.infrastructure.persistence.repositories.swiss_stock_repository import (  # noqa: E402
    SQLASwissStockRepository,
)


def _make_market_svc(session: AsyncSession) -> SwissMarketService:
    return SwissMarketService(repo=SQLASwissStockRepository(session=session))


@_register("search_stocks")
async def _search_stocks(inputs: dict[str, Any], session: AsyncSession) -> str:
    query = (inputs.get("query") or "").lower()
    svc = _make_market_svc(session)
    all_stocks = await svc.list_smi_stocks()
    results = [s for s in all_stocks if query in s.ticker.lower() or query in (s.name or "").lower()]
    return json.dumps([{"ticker": s.ticker, "name": s.name} for s in results[:10]])


@_register("filter_stocks")
async def _filter_stocks(inputs: dict[str, Any], session: AsyncSession) -> str:
    svc = _make_market_svc(session)
    stocks = await svc.list_smi_stocks()
    signal_filter = inputs.get("signal")
    eligible_filter = inputs.get("eligible_3a")
    min_score = inputs.get("min_score", 0)
    filtered = [
        s for s in stocks
        if (not signal_filter or getattr(s, "signal", None) == signal_filter)
        and (not eligible_filter or getattr(s, "eligible_3a", False))
        and (getattr(s, "quant_score", None) or 0) >= min_score
    ]
    return json.dumps([
        {"ticker": s.ticker, "signal": getattr(s, "signal", None), "score": getattr(s, "quant_score", None)}
        for s in filtered[:15]
    ])


@_register("get_factsheet")
async def _get_factsheet(inputs: dict[str, Any], session: AsyncSession) -> str:
    svc = _make_market_svc(session)
    data = await svc.get_swiss_stock(inputs["ticker"])
    if data is None:
        return f"Keine Daten für {inputs['ticker']} gefunden."
    return json.dumps({
        "ticker": data.ticker,
        "signal": getattr(data, "signal", None),
        "quant_score": getattr(data, "quant_score", None),
        "eligible_3a": getattr(data, "eligible_3a", None),
    })


@_register("get_macro_context")
async def _get_macro_context(inputs: dict[str, Any], session: AsyncSession) -> str:
    ctx = await MacroService().get_context()
    return json.dumps({"snb_rate": ctx.leitzins, "chf_eur": ctx.chf_eur, "inflation_ch": ctx.inflation_ch})


@_register("compare_stocks")
async def _compare_stocks(inputs: dict[str, Any], session: AsyncSession) -> str:
    svc = _make_market_svc(session)
    a = await svc.get_swiss_stock(inputs["ticker_a"])
    b = await svc.get_swiss_stock(inputs["ticker_b"])
    return json.dumps({
        inputs["ticker_a"]: {"signal": getattr(a, "signal", None) if a else None, "score": getattr(a, "quant_score", None) if a else None},
        inputs["ticker_b"]: {"signal": getattr(b, "signal", None) if b else None, "score": getattr(b, "quant_score", None) if b else None},
    })


@_register("get_ranking")
async def _get_ranking(inputs: dict[str, Any], session: AsyncSession) -> str:
    svc = _make_market_svc(session)
    stocks = await svc.list_smi_stocks()
    top_n = inputs.get("top_n", 5)
    ranked = sorted(stocks, key=lambda s: getattr(s, "quant_score", None) or 0, reverse=True)[:top_n]
    return json.dumps([
        {"ticker": s.ticker, "signal": getattr(s, "signal", None), "score": getattr(s, "quant_score", None)}
        for s in ranked
    ])


# ---------------------------------------------------------------------------
# Tool-Definitionen für Claude API
# ---------------------------------------------------------------------------

_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_stocks",
        "description": "Sucht Aktien im PRISMA-Universum nach Name oder Ticker-Symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Suchbegriff: Firmenname oder Ticker"},
                "exchange": {"type": "string", "description": "Optional: 'SW' für Swiss, 'US' für US-Markt"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "filter_stocks",
        "description": "Filtert Aktien nach quantitativen Kriterien.",
        "input_schema": {
            "type": "object",
            "properties": {
                "signal": {"type": "string", "enum": ["BUY", "HOLD", "WATCH"], "description": "Swiss Quant Signal"},
                "eligible_3a": {"type": "boolean", "description": "Nur 3a-geeignete Titel"},
                "min_score": {"type": "number", "description": "Minimum Quant-Score (0–100)"},
                "universe": {"type": "string", "description": "SMI | SMIM | SPI"},
            },
        },
    },
    {
        "name": "get_factsheet",
        "description": "Detaillierte Analyse: Quant-Scores, ML-Prediction, Fundamentaldaten, 3a-Eignung.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Ticker-Symbol, z.B. NESN.SW oder AAPL"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_macro_context",
        "description": "Aktueller SNB-Leitzins, CHF/EUR-Kurs, Schweizer Inflation.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "compare_stocks",
        "description": "Vergleicht zwei Aktien anhand Quant-Scores, ML-Signal und Fundamentaldaten.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker_a": {"type": "string"}, "ticker_b": {"type": "string"}},
            "required": ["ticker_a", "ticker_b"],
        },
    },
    {
        "name": "get_ranking",
        "description": "Top-N Aktien aus einem Universum, sortiert nach gewichtetem Quant-Score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "universe": {"type": "string", "description": "SMI | SMIM | SPI | US"},
                "top_n": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# ChatService
# ---------------------------------------------------------------------------


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class ChatService:
    """Orchestriert Claude mit PRISMA-Tools für Konversations-Interface."""

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Streamt SSE-Events: token | tool_call | tool_result | done."""
        import anthropic

        client = anthropic.AsyncAnthropic()
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            async with client.messages.stream(
                model=_MODEL,
                max_tokens=1024,
                system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=cast(Any, _TOOL_DEFINITIONS),
                messages=cast(Any, api_messages),
            ) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                            yield _sse("token", {"content": event.delta.text})
                        elif (
                            event.type == "content_block_start"
                            and hasattr(event.content_block, "type")
                            and event.content_block.type == "tool_use"
                        ):
                            yield _sse("tool_call", {"tool": event.content_block.name, "tool_use_id": event.content_block.id})

                final = await stream.get_final_message()

            if final.stop_reason == "tool_use":
                tool_results = []
                for block in final.content:
                    if block.type == "tool_use":
                        yield _sse("tool_call", {"tool": block.name, "input": block.input})
                        result_str = await _dispatch_tool(block.name, block.input)
                        if len(result_str) > _TOOL_RESULT_MAX_CHARS:
                            _logger.debug("Tool '%s' Ergebnis auf %d Zeichen gekürzt (war %d)", block.name, _TOOL_RESULT_MAX_CHARS, len(result_str))
                            result_str = result_str[:_TOOL_RESULT_MAX_CHARS]
                        yield _sse("tool_result", {"tool": block.name, "result": result_str})
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})

                continuation_messages = api_messages + [
                    {"role": "assistant", "content": final.content},
                    {"role": "user", "content": tool_results},
                ]
                async with client.messages.stream(
                    model=_MODEL,
                    max_tokens=1024,
                    system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                    messages=cast(Any, continuation_messages),
                ) as stream2:
                    async for event in stream2:
                        if hasattr(event, "type") and event.type == "content_block_delta" and hasattr(event.delta, "text"):
                            yield _sse("token", {"content": event.delta.text})

        except Exception:
            _logger.exception("ChatService stream error")
            yield _sse("error", {"message": "Interner Fehler — bitte nochmals versuchen."})

        yield _sse("done", {})


def _sse(event_type: str, data: dict[str, Any]) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


async def _dispatch_tool(name: str, inputs: dict[str, Any]) -> str:
    """Leitet Tool-Call über Registry an entsprechenden Handler weiter."""
    handler = _TOOL_REGISTRY.get(name)
    if handler is None:
        return json.dumps({"error": f"Tool '{name}' nicht registriert. Bekannte Tools: {list(_TOOL_REGISTRY)}"})

    try:
        from backend.infrastructure.persistence.session import get_session_factory
        async with get_session_factory()() as session:
            return await handler(inputs, session)
    except Exception as exc:
        _logger.warning("Tool dispatch error: %s — %s", name, exc)
        return json.dumps({"error": str(exc)})
