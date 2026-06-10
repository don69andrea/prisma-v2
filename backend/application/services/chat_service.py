"""Application Service: PRISMA Chat — Claude Tool Use + SSE Streaming."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist PRISMA Assistant — ein präziser, datengetriebener Finanz-Assistent.
Du hast Zugriff auf das PRISMA-Universum (SMI/SMIM/SPI + US-Aktien) via Tools.
Antworte IMMER auf Basis der Tool-Ergebnisse — nie aus deinem Trainingswissen über aktuelle Preise.
Sprache: Deutsch bevorzugt. Englisch wenn der Nutzer auf Englisch schreibt.
Bei konkreten Kauf-/Verkaufsempfehlungen: füge immer hinzu "Keine Anlageberatung."
Sei präzise und knapp — maximal 3 Absätze pro Antwort."""

_MODEL = "claude-sonnet-4-6"


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class ChatService:
    """Orchestriert Claude mit PRISMA-Tools für Konversations-Interface."""

    def _get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "search_stocks",
                "description": "Sucht Aktien im PRISMA-Universum nach Name oder Ticker-Symbol.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Suchbegriff: Firmenname oder Ticker",
                        },
                        "exchange": {
                            "type": "string",
                            "description": "Optional: 'SW' für Swiss, 'US' für US-Markt",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "filter_stocks",
                "description": (
                    "Filtert Aktien nach quantitativen Kriterien. "
                    "Gibt Liste von Titeln zurück die alle Bedingungen erfüllen."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "signal": {
                            "type": "string",
                            "enum": ["BUY", "HOLD", "WATCH"],
                            "description": "Swiss Quant Signal",
                        },
                        "eligible_3a": {"type": "boolean", "description": "Nur 3a-geeignete Titel"},
                        "min_score": {
                            "type": "number",
                            "description": "Minimum Quant-Score (0–100)",
                        },
                        "universe": {"type": "string", "description": "SMI | SMIM | SPI"},
                    },
                },
            },
            {
                "name": "get_factsheet",
                "description": "Detaillierte Analyse: Quant-Scores, ML-Prediction, Fundamentaldaten, 3a-Eignung.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Ticker-Symbol, z.B. NESN.SW oder AAPL",
                        },
                    },
                    "required": ["ticker"],
                },
            },
            {
                "name": "get_macro_context",
                "description": "Aktueller SNB-Leitzins, CHF/EUR-Kurs, Schweizer Inflation — makroökonomischer Kontext.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "compare_stocks",
                "description": "Vergleicht zwei Aktien anhand Quant-Scores, ML-Signal und Fundamentaldaten.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker_a": {"type": "string"},
                        "ticker_b": {"type": "string"},
                    },
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

    async def stream(
        self,
        messages: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """Streamt SSE-Events: token | tool_call | tool_result | done."""
        import anthropic

        client = anthropic.AsyncAnthropic()
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            async with client.messages.stream(
                model=_MODEL,
                max_tokens=1024,
                system=[
                    {"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
                ],
                tools=self._get_tool_definitions(),
                messages=api_messages,
            ) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield _sse("token", {"content": event.delta.text})
                        elif (
                            event.type == "content_block_start"
                            and hasattr(event.content_block, "type")
                            and event.content_block.type == "tool_use"
                        ):
                            yield _sse(
                                "tool_call",
                                {
                                    "tool": event.content_block.name,
                                    "tool_use_id": event.content_block.id,
                                },
                            )

                final = await stream.get_final_message()

            if final.stop_reason == "tool_use":
                tool_results = []
                for block in final.content:
                    if block.type == "tool_use":
                        yield _sse("tool_call", {"tool": block.name, "input": block.input})
                        result_str = await _dispatch_tool(block.name, block.input)
                        yield _sse("tool_result", {"tool": block.name, "result": result_str[:500]})
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_str,
                            }
                        )

                continuation_messages = api_messages + [
                    {"role": "assistant", "content": final.content},
                    {"role": "user", "content": tool_results},
                ]
                async with client.messages.stream(
                    model=_MODEL,
                    max_tokens=1024,
                    system=[
                        {
                            "type": "text",
                            "text": _SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=continuation_messages,
                ) as stream2:
                    async for event in stream2:
                        if (
                            hasattr(event, "type")
                            and event.type == "content_block_delta"
                            and hasattr(event.delta, "text")
                        ):
                            yield _sse("token", {"content": event.delta.text})

        except Exception:
            _logger.exception("ChatService stream error")
            yield _sse("error", {"message": "Interner Fehler — bitte nochmals versuchen."})

        yield _sse("done", {})


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


async def _dispatch_tool(name: str, inputs: dict) -> str:
    """Leitet Tool-Call an entsprechenden Application Service weiter."""
    try:
        if name == "search_stocks":
            svc = _get_stock_service()
            results = await svc.search(inputs.get("query", ""))
            return json.dumps([{"ticker": s.ticker, "name": s.name} for s in results[:10]])

        if name == "filter_stocks":
            from backend.application.services.swiss_market_service import SwissMarketService
            from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

            svc = SwissMarketService(adapter=YFinanceSwissAdapter())
            stocks = await svc.list_stocks(
                signal=inputs.get("signal"),
                eligible_3a=inputs.get("eligible_3a"),
            )
            min_score = inputs.get("min_score", 0)
            filtered = [s for s in stocks if (s.quant_score or 0) >= min_score]
            return json.dumps(
                [
                    {"ticker": s.ticker, "signal": s.signal, "score": s.quant_score}
                    for s in filtered[:15]
                ]
            )

        if name == "get_factsheet":
            from backend.application.services.factsheet_service import FactsheetService
            from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
                SQLASwissStockRepository,
            )
            from backend.infrastructure.persistence.session import get_session_factory

            repo = SQLASwissStockRepository(session_factory=get_session_factory())
            svc = FactsheetService(swiss_stock_repo=repo)
            data = await svc.get(inputs["ticker"])
            if data is None:
                return f"Keine Daten für {inputs['ticker']} gefunden."
            return json.dumps(
                {
                    "ticker": data.ticker,
                    "signal": data.signal,
                    "quant_score": data.quant_score,
                    "eligible_3a": data.eligible_3a,
                }
            )

        if name == "get_macro_context":
            from backend.application.services.macro_service import MacroService

            svc = MacroService()
            ctx = await svc.get_context()
            return json.dumps(
                {
                    "snb_rate": ctx.snb_rate,
                    "chf_eur": ctx.chf_eur,
                    "inflation_ch": ctx.inflation_ch,
                }
            )

        if name == "compare_stocks":
            from backend.application.services.factsheet_service import FactsheetService
            from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
                SQLASwissStockRepository,
            )
            from backend.infrastructure.persistence.session import get_session_factory

            repo = SQLASwissStockRepository(session_factory=get_session_factory())
            svc = FactsheetService(swiss_stock_repo=repo)
            a = await svc.get(inputs["ticker_a"])
            b = await svc.get(inputs["ticker_b"])
            return json.dumps(
                {
                    inputs["ticker_a"]: {
                        "signal": a.signal if a else None,
                        "score": a.quant_score if a else None,
                    },
                    inputs["ticker_b"]: {
                        "signal": b.signal if b else None,
                        "score": b.quant_score if b else None,
                    },
                }
            )

        if name == "get_ranking":
            from backend.application.services.swiss_market_service import SwissMarketService
            from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

            svc = SwissMarketService(adapter=YFinanceSwissAdapter())
            stocks = await svc.list_stocks()
            top_n = inputs.get("top_n", 5)
            ranked = sorted(stocks, key=lambda s: s.quant_score or 0, reverse=True)[:top_n]
            return json.dumps(
                [{"ticker": s.ticker, "signal": s.signal, "score": s.quant_score} for s in ranked]
            )

        return json.dumps({"error": f"Tool '{name}' unbekannt."})

    except Exception as exc:
        _logger.warning("Tool dispatch error: %s — %s", name, exc)
        return json.dumps({"error": str(exc)})


def _get_stock_service():
    from backend.application.services.stock_service import StockService
    from backend.infrastructure.persistence.repositories.stock_repository import SQLAStockRepository
    from backend.infrastructure.persistence.session import get_session_factory

    return StockService(stock_repo=SQLAStockRepository(session_factory=get_session_factory()))
