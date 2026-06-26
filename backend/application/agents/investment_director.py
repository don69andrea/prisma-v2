"""InvestmentDirector — SSE-Orchestrator mit HITL-Checkpoints.

Fan-out: MacroAgentV2 + StockService (Quant) + SteuerAgent (parallel)
HITL:   asyncio.Event wartet auf User-Antwort über /checkpoint-Endpoint
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

_logger = logging.getLogger(__name__)
_CHECKPOINT_TIMEOUT = 600  # 10 Minuten


class InvestmentDirector:
    def __init__(
        self,
        macro_agent: Any,
        stock_service: Any,
        steuer_agent: Any,
    ) -> None:
        self._macro = macro_agent
        self._stocks = stock_service
        self._steuer = steuer_agent
        self._checkpoints: dict[str, asyncio.Event] = {}
        self._checkpoint_answers: dict[str, str | None] = {}

    async def run_with_events(
        self,
        ticker: str,
        context: str,
        run_id: str,
        event_queue: asyncio.Queue[Any],
    ) -> None:
        """Orchestriert alle Agents und schreibt Events in die Queue."""

        async def emit(event: dict[str, Any]) -> None:
            await event_queue.put(event)

        await emit(
            {
                "type": "step",
                "agent": "Director",
                "status": "planning",
                "result": f"Starte Analyse für {ticker}...",
            }
        )

        # Fan-out: Macro + Quant parallel
        await emit({"type": "step", "agent": "MacroAgent V2", "status": "running"})
        await emit({"type": "step", "agent": "QuantAgent", "status": "running"})

        macro_task = asyncio.create_task(self._run_macro(ticker))
        quant_task = asyncio.create_task(self._run_quant(ticker))

        results = await asyncio.gather(macro_task, quant_task, return_exceptions=True)
        macro_result: Any = results[0]
        quant_result: Any = results[1]

        if isinstance(macro_result, Exception):
            await emit(
                {
                    "type": "step",
                    "agent": "MacroAgent V2",
                    "status": "error",
                    "result": str(macro_result),
                }
            )
            macro_result = None
        else:
            await emit(
                {
                    "type": "step",
                    "agent": "MacroAgent V2",
                    "status": "done",
                    "result": f"Score: {macro_result.score:.0f}/100 | {macro_result.chf_impact}",
                }
            )

        if isinstance(quant_result, Exception):
            await emit(
                {
                    "type": "step",
                    "agent": "QuantAgent",
                    "status": "error",
                    "result": str(quant_result),
                }
            )
            quant_result = None
        else:
            signal = getattr(quant_result, "signal", "?")
            score = getattr(quant_result, "quant_score", 0)
            await emit(
                {
                    "type": "step",
                    "agent": "QuantAgent",
                    "status": "done",
                    "result": f"Signal: {signal} | Score: {score:.0f}",
                }
            )

        # HITL: Kontext klären falls unbekannt
        if context == "unknown":
            cp_id = f"cp_{uuid.uuid4().hex[:8]}"
            await emit(
                {
                    "type": "checkpoint",
                    "checkpoint_id": cp_id,
                    "message": f"Für welches Konto analysiere ich {ticker}?",
                    "options": ["3a-Konto (VIAC)", "Freie Mittel", "Beides analysieren"],
                }
            )
            context = await self._wait_for_checkpoint(cp_id)

        anlegerprofil = "vorsorge_3a" if "3a" in context.lower() else "privatperson"

        # SteuerAgent
        await emit({"type": "step", "agent": "SteuerAgent", "status": "running"})
        try:
            steuer_result = await self._steuer.einschaetzen(
                ticker=ticker,
                anlegerprofil=anlegerprofil,
                halteperiode_jahre=3,
            )
            await emit(
                {
                    "type": "step",
                    "agent": "SteuerAgent",
                    "status": "done",
                    "result": f"{anlegerprofil} | {', '.join(steuer_result.steuerarten[:2])}",
                }
            )
        except Exception as exc:
            _logger.warning("SteuerAgent fehlgeschlagen: %s", exc)
            steuer_result = None
            await emit(
                {"type": "step", "agent": "SteuerAgent", "status": "error", "result": str(exc)}
            )

        signal = getattr(quant_result, "signal", "HOLD") if quant_result else "HOLD"
        confidence = self._calc_confidence(macro_result, quant_result)

        await emit(
            {
                "type": "done",
                "run_id": run_id,
                "signal": signal,
                "confidence": confidence,
                "report": {
                    "ticker": ticker,
                    "context": context,
                    "macro_score": macro_result.score if macro_result else None,
                    "macro_reasoning": macro_result.reasoning if macro_result else None,
                    "chf_impact": macro_result.chf_impact if macro_result else None,
                    "quant_signal": getattr(quant_result, "signal", None),
                    "quant_score": getattr(quant_result, "quant_score", None),
                    "steuer_arten": steuer_result.steuerarten if steuer_result else [],
                    "steuer_hinweise": steuer_result.hinweise[:2] if steuer_result else [],
                    "anlegerprofil": anlegerprofil,
                },
            }
        )

    async def resolve_checkpoint(self, checkpoint_id: str, answer: str) -> None:
        """Vom Checkpoint-Endpoint aufgerufen wenn User antwortet."""
        self._checkpoint_answers[checkpoint_id] = answer
        event = self._checkpoints.get(checkpoint_id)
        if event:
            event.set()

    async def _wait_for_checkpoint(self, cp_id: str) -> str:
        event = asyncio.Event()
        self._checkpoints[cp_id] = event
        self._checkpoint_answers[cp_id] = None
        try:
            await asyncio.wait_for(event.wait(), timeout=_CHECKPOINT_TIMEOUT)
        except TimeoutError:
            _logger.warning("Checkpoint %s timed out nach %ds", cp_id, _CHECKPOINT_TIMEOUT)
        finally:
            self._checkpoints.pop(cp_id, None)
        return self._checkpoint_answers.pop(cp_id, None) or "freie_mittel"

    async def _run_macro(self, ticker: str) -> Any:
        return await self._macro.get_macro_report(ticker)

    async def _run_quant(self, ticker: str) -> Any:
        return await self._stocks.get_decision(ticker)

    @staticmethod
    def _calc_confidence(macro: Any, quant: Any) -> float:
        score = 0.5
        if macro is not None:
            score += (macro.score - 50) / 200
        if quant is not None:
            qs = getattr(quant, "quant_score", 50)
            score += (qs - 50) / 200
        return round(min(max(score, 0.0), 1.0), 3)
