"""LLMClient — Single-Entry-Wrapper über Anthropic + Voyage SDKs.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §4.

Aufrufer (Narrative-Engine, Multi-Agent-Pipeline, RAG-Ingestion) nutzen
ausschliesslich diesen Wrapper — kein direkter SDK-Import in der
Application-Schicht (AGENTS.md/CLAUDE.md-Regel).

Vor jedem Call: `CostTracker.check_cap()` prüft Budget. Nach erfolgreichem
Call: `CostTracker.record()` schreibt eine Audit-Zeile mit den tatsächlichen
Token-Counts und Kosten.
"""

import asyncio
from decimal import Decimal
from typing import Any

from backend.application.services.cost_tracker import CostTracker
from backend.domain.errors import UnknownModelError
from backend.infrastructure.llm.pricing import PRICING

_ONE_MILLION = Decimal("1_000_000")

# Konservativer Token-Estimator: ~3 chars/token. Anthropic-Tokenizer
# liefert empirisch ~4 chars/token für Englisch, aber DE-Texte und
# Code-Snippets brechen das deutlich nach unten. Einen zu *niedrigen*
# Faktor zu wählen unterschätzt die Kosten und macht die Cap-Schwelle
# leck — wir bleiben bewusst auf der pessimistischen Seite.
_CHARS_PER_TOKEN_ESTIMATE = 3


class LLMClient:
    def __init__(
        self,
        *,
        anthropic: Any,
        voyage: Any,
        cost_tracker: CostTracker,
    ) -> None:
        self._anthropic = anthropic
        self._voyage = voyage
        self._cost_tracker = cost_tracker

    async def messages_create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        feature: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Wrapper um `anthropic.messages.create` mit Cap-Check + Audit-Logging.

        `feature` ist Pflicht-Parameter (kein Default) — Aufrufer MUSS taggen,
        sonst wird das Audit-Log unbrauchbar.
        """
        estimated_usd = self._estimate_messages_cost(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            system=system,
        )
        await self._cost_tracker.check_cap(estimated_usd=estimated_usd)

        sdk_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if system is not None:
            sdk_kwargs["system"] = system

        response = await self._anthropic.messages.create(**sdk_kwargs)

        await self._cost_tracker.record(
            provider="anthropic",
            model=model,
            feature=feature,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            request_id=response.id,
        )
        return response

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
        feature: str,
    ) -> list[list[float]]:
        """Wrapper um `voyage.embed` mit Cap-Check + Audit-Logging.

        Voyage-SDK ist sync — Aufruf läuft in einem Thread-Pool, damit der
        Event-Loop nicht blockiert wird.
        """
        try:
            pricing = PRICING[model]
        except KeyError as exc:
            raise UnknownModelError(model, reason="nicht in PRICING-Registry") from exc
        if pricing.embed_per_mtok is None:
            raise UnknownModelError(model, reason="kein Embed-Pricing — verwende messages_create")

        chars = sum(len(t) for t in texts)
        estimated_usd = (
            Decimal(chars // _CHARS_PER_TOKEN_ESTIMATE) * pricing.embed_per_mtok / _ONE_MILLION
        )
        await self._cost_tracker.check_cap(estimated_usd=estimated_usd)

        # Voyage Python SDK ist synchron; in den Thread-Pool auslagern,
        # sonst blockiert die Event-Loop bei grossen Batches.
        response = await asyncio.to_thread(self._voyage.embed, texts, model=model)

        await self._cost_tracker.record(
            provider="voyage",
            model=model,
            feature=feature,
            input_tokens=response.total_tokens,
            output_tokens=0,
        )
        return list(response.embeddings)

    @staticmethod
    def _estimate_messages_cost(
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        system: str | None,
    ) -> Decimal:
        """chars/3 für Input (konservativ, siehe Modul-Konstante) + max_tokens
        als worst-case Output."""
        try:
            pricing = PRICING[model]
        except KeyError as exc:
            raise UnknownModelError(model, reason="nicht in PRICING-Registry") from exc
        if pricing.input_per_mtok is None or pricing.output_per_mtok is None:
            raise UnknownModelError(model, reason="kein Chat-Pricing — verwende embed")
        chars = sum(len(m.get("content", "")) for m in messages)
        if system:
            chars += len(system)
        input_tokens_est = chars // _CHARS_PER_TOKEN_ESTIMATE
        return (
            Decimal(input_tokens_est) * pricing.input_per_mtok / _ONE_MILLION
            + Decimal(max_tokens) * pricing.output_per_mtok / _ONE_MILLION
        )
