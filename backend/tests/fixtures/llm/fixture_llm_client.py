"""FixtureLLMClient — deterministische Test-Implementierung des LLMClient-Interfaces.

Bundelt StubAnthropicClient + LLMClient + NullCostTracker in einem Schritt,
sodass Integration-Tests den LLM-Stack ohne DB-Abhängigkeit aufbauen können.

Typische Verwendung in Tests:

    fixture_client = FixtureLLMClient([FIXTURES / "top_quality_stock.json"])
    service = NarrativeService(..., llm_client=fixture_client.llm, ...)
    await service.generate_memo(...)
    assert fixture_client.calls[0]["model"] == "claude-sonnet-4-6"
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.application.services.cost_tracker import CostTracker
from backend.domain.cost_summary import CostBreakdown
from backend.domain.repositories.cost_log_repository import CostLogEntry, CostLogRepository
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.pricing import PRICING
from backend.tests.fixtures.llm.stub_anthropic_client import StubAnthropicClient


class _NullCostLogRepository(CostLogRepository):
    """No-op CostLogRepository — verwirft alle Einträge, meldet 0 Kosten.

    Nur für Tests ohne DB-Verbindung gedacht.
    """

    async def record(self, entry: CostLogEntry) -> None:
        pass

    async def current_month_total_usd(self) -> Decimal:
        return Decimal("0")

    async def current_month_breakdown(self, last_n: int) -> CostBreakdown:
        return CostBreakdown(by_model=[], by_feature=[], last_calls=[])


class FixtureLLMClient:
    """Kombiniert StubAnthropicClient + LLMClient für fixture-basierte Tests.

    Eliminiert den Setup-Boilerplate in Integration-Tests:
    - StubAnthropicClient wird intern aufgebaut
    - LLMClient wird mit NullCostTracker konfiguriert
    - .llm gibt den fertigen LLMClient zurück
    - .calls gibt die Liste der SDK-Aufrufe zurück (für Assertions)
    """

    def __init__(
        self,
        fixture_paths: list[Path],
        cap_usd: Decimal = Decimal("20"),
    ) -> None:
        self._stub = StubAnthropicClient(fixture_paths)
        self.cost_tracker = CostTracker(
            repository=_NullCostLogRepository(),
            pricing=PRICING,
            cap_usd=cap_usd,
        )
        self.llm = LLMClient(
            anthropic=self._stub,
            voyage=None,
            cost_tracker=self.cost_tracker,
            pricing=PRICING,
        )

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._stub.messages.calls
