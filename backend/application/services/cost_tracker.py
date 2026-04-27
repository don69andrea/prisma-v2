"""CostTracker — Application-Service für Cap-Checks, Cost-Recording und Summary.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §5 + §9.

Dünner Service über dem CostLogRepository-Port — keine SQLAlchemy-/ORM-
Imports (AGENTS.md §2).

Wird vom `LLMClient`-Wrapper in der Infrastructure-Schicht aufgerufen:
- `check_cap(estimated_usd)` vor jedem LLM-Call: wirft `BudgetCapExceeded`,
  wenn das Monats-Budget um die Schätzung überschritten würde
- `record(...)` nach jedem erfolgreichen Call: berechnet Kosten aus Tokens
  und delegiert das Persistieren an den Repository-Adapter
- `summary(last_n)` liefert aggregierte Kosten-Übersicht für den Admin-Endpoint

Concurrency: das App-Cap ist ein **Soft-Limit** — ein kleines Race-Window
existiert (zwei parallele Calls passen beide `check_cap` und schreiben dann
beide `record`). Bei Capstone-Volumen (max ~30 Calls/Batch) absorbiert die
5%-Schwelle das. Der echte **Backstop** ist das Anthropic-Console Spend-Limit.
"""

from datetime import UTC, datetime
from decimal import Decimal

from backend.domain.cost_summary import CostSummary
from backend.domain.errors import BudgetCapExceeded, UnknownModelError
from backend.domain.repositories.cost_log_repository import (
    CostLogEntry,
    CostLogRepository,
)
from backend.infrastructure.llm.pricing import PRICING


class CostTracker:
    def __init__(
        self,
        *,
        repository: CostLogRepository,
        cap_usd: Decimal,
        threshold: Decimal = Decimal("0.95"),
    ) -> None:
        self._repository = repository
        self._cap_usd = cap_usd
        self._threshold = threshold

    async def check_cap(self, *, estimated_usd: Decimal) -> None:
        """Wirft BudgetCapExceeded, wenn (current + estimated) > cap * threshold."""
        current = await self._repository.current_month_total_usd()
        if (current + estimated_usd) > self._cap_usd * self._threshold:
            raise BudgetCapExceeded(
                current_usd=current,
                attempted_usd=estimated_usd,
                cap_usd=self._cap_usd,
            )

    async def record(
        self,
        *,
        provider: str,
        model: str,
        feature: str,
        input_tokens: int,
        output_tokens: int,
        request_id: str | None = None,
    ) -> None:
        """Berechnet Kosten aus Tokens und delegiert an Repository.

        Repository-Adapter persistiert in eigener Transaktion (siehe
        `SQLACostLogRepository.record`).
        """
        cost_usd = self._compute_cost_usd(model, input_tokens, output_tokens)
        await self._repository.record(
            CostLogEntry(
                provider=provider,
                model=model,
                feature=feature,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                request_id=request_id,
            )
        )

    async def summary(self, *, last_n: int = 10) -> CostSummary:
        """Liefert aggregierte Kosten-Übersicht für den aktuellen Kalender-Monat UTC.

        Spezifiziert in §9.
        """
        month = datetime.now(UTC).strftime("%Y-%m")
        current_usd = await self._repository.current_month_total_usd()
        breakdown = await self._repository.current_month_breakdown(last_n)
        remaining_usd = max(self._cap_usd - current_usd, Decimal("0"))
        return CostSummary(
            month=month,
            cap_usd=self._cap_usd,
            current_usd=current_usd,
            remaining_usd=remaining_usd,
            by_model=breakdown.by_model,
            by_feature=breakdown.by_feature,
            last_calls=breakdown.last_calls,
        )

    @staticmethod
    def _compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
        """Token-Counts → Kosten in USD via PRICING-Registry.

        Embedding-Modelle (embed_per_mtok ist gesetzt) verwenden nur
        input_tokens; Chat-Modelle verwenden input + output. Wirft
        `UnknownModelError` bei unbekannten oder fehlerhaft konfigurierten
        Modellen — kein blanker `KeyError`.
        """
        try:
            pricing = PRICING[model]
        except KeyError as exc:
            raise UnknownModelError(model, reason="nicht in PRICING-Registry") from exc

        million = Decimal("1_000_000")
        if pricing.embed_per_mtok is not None:
            return Decimal(input_tokens) * pricing.embed_per_mtok / million
        if pricing.input_per_mtok is None or pricing.output_per_mtok is None:
            raise UnknownModelError(
                model,
                reason="weder Chat- noch Embed-Pricing gesetzt — Registry-Bug",
            )
        return (
            Decimal(input_tokens) * pricing.input_per_mtok / million
            + Decimal(output_tokens) * pricing.output_per_mtok / million
        )
