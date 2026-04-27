"""Unit-Tests für CostTracker — Service-Verhalten gegen Mock-Repository.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §5 + §9 + §10.2.

Tests bauen direkt gegen den `CostLogRepository`-Port — keine SQLAlchemy-
oder ORM-Imports mehr (AGENTS.md §2).
"""

import re
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from backend.application.services.cost_tracker import CostTracker
from backend.domain.cost_summary import (
    CallEntry,
    CostBreakdown,
    FeatureBreakdown,
    ModelBreakdown,
)
from backend.domain.errors import BudgetCapExceeded
from backend.domain.repositories.cost_log_repository import (
    CostLogEntry,
    CostLogRepository,
)

pytestmark = pytest.mark.unit


def _make_repository(
    *,
    current_total: Decimal = Decimal("0"),
    breakdown: CostBreakdown | None = None,
) -> AsyncMock:
    """Minimaler Mock des CostLogRepository-Ports."""
    repo = AsyncMock(spec=CostLogRepository)
    repo.current_month_total_usd = AsyncMock(return_value=current_total)
    repo.record = AsyncMock(return_value=None)
    repo.current_month_breakdown = AsyncMock(
        return_value=breakdown or CostBreakdown(by_model=[], by_feature=[], last_calls=[])
    )
    return repo


def _make_tracker(
    *,
    repository: AsyncMock | None = None,
    cap: str = "100.00",
    threshold: str = "0.95",
) -> CostTracker:
    return CostTracker(
        repository=repository or _make_repository(),
        cap_usd=Decimal(cap),
        threshold=Decimal(threshold),
    )


class TestCheckCap:
    async def test_below_threshold_does_not_raise(self) -> None:
        # cap=100, threshold=0.95 → Schwelle bei 95.00.
        # current 94.99 + estimate 0.01 = 95.00 → exakt an Schwelle, nicht >.
        repo = _make_repository(current_total=Decimal("94.99"))
        tracker = _make_tracker(repository=repo)
        await tracker.check_cap(estimated_usd=Decimal("0.01"))  # darf nicht werfen

    async def test_exactly_at_threshold_does_not_raise(self) -> None:
        repo = _make_repository(current_total=Decimal("95.00"))
        tracker = _make_tracker(repository=repo)
        # 95.00 + 0.00 = 95.00 → nicht > 95.00, also kein Fehler
        await tracker.check_cap(estimated_usd=Decimal("0.00"))

    async def test_just_above_threshold_raises(self) -> None:
        repo = _make_repository(current_total=Decimal("95.00"))
        tracker = _make_tracker(repository=repo)
        # 95.00 + 0.01 = 95.01 → > 95.00, Fehler
        with pytest.raises(BudgetCapExceeded):
            await tracker.check_cap(estimated_usd=Decimal("0.01"))

    async def test_far_above_threshold_raises(self) -> None:
        repo = _make_repository(current_total=Decimal("99.50"))
        tracker = _make_tracker(repository=repo)
        with pytest.raises(BudgetCapExceeded):
            await tracker.check_cap(estimated_usd=Decimal("0.60"))

    async def test_exception_carries_correct_amounts(self) -> None:
        repo = _make_repository(current_total=Decimal("99.50"))
        tracker = _make_tracker(repository=repo)
        with pytest.raises(BudgetCapExceeded) as exc_info:
            await tracker.check_cap(estimated_usd=Decimal("0.60"))
        assert exc_info.value.current_usd == Decimal("99.50")
        assert exc_info.value.attempted_usd == Decimal("0.60")
        assert exc_info.value.cap_usd == Decimal("100.00")

    async def test_custom_threshold(self) -> None:
        repo = _make_repository(current_total=Decimal("50.00"))
        tracker = _make_tracker(repository=repo, threshold="0.50")
        # 50.00 + 0.01 = 50.01 → > 50.00, Fehler bei 50% threshold
        with pytest.raises(BudgetCapExceeded):
            await tracker.check_cap(estimated_usd=Decimal("0.01"))


class TestRecord:
    async def test_creates_log_entry_for_chat_model(self) -> None:
        repo = _make_repository()
        tracker = _make_tracker(repository=repo)
        await tracker.record(
            provider="anthropic",
            model="claude-sonnet-4-6",
            feature="narrative_engine",
            input_tokens=1_000_000,
            output_tokens=500_000,
            request_id="msg_abc",
        )

        repo.record.assert_called_once()
        entry: CostLogEntry = repo.record.call_args.args[0]
        assert entry.provider == "anthropic"
        assert entry.model == "claude-sonnet-4-6"
        assert entry.feature == "narrative_engine"
        assert entry.input_tokens == 1_000_000
        assert entry.output_tokens == 500_000
        # 1M input @ $3 + 0.5M output @ $15 = 3.00 + 7.50 = 10.50
        assert entry.cost_usd == Decimal("10.50")
        assert entry.request_id == "msg_abc"

    async def test_creates_log_entry_for_embed_model(self) -> None:
        repo = _make_repository()
        tracker = _make_tracker(repository=repo)
        await tracker.record(
            provider="voyage",
            model="voyage-3-large",
            feature="rag_ingestion",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        entry: CostLogEntry = repo.record.call_args.args[0]
        # 1M tokens @ $0.18/M = 0.18
        assert entry.cost_usd == Decimal("0.18")
        assert entry.provider == "voyage"

    async def test_request_id_defaults_to_none(self) -> None:
        repo = _make_repository()
        tracker = _make_tracker(repository=repo)
        await tracker.record(
            provider="anthropic",
            model="claude-haiku-4-5",
            feature="test_feature",
            input_tokens=1000,
            output_tokens=1000,
        )
        entry: CostLogEntry = repo.record.call_args.args[0]
        assert entry.request_id is None


class TestSummary:
    async def test_returns_current_month_string_in_yyyy_mm_format(self) -> None:
        """month-Feld muss dem Muster YYYY-MM entsprechen."""
        tracker = _make_tracker()
        summary = await tracker.summary(last_n=10)
        assert re.match(r"^\d{4}-\d{2}$", summary.month)

    async def test_remaining_usd_is_cap_minus_current_when_under(self) -> None:
        """remaining_usd = cap - current, wenn current < cap."""
        repo = _make_repository(current_total=Decimal("10.00"))
        tracker = _make_tracker(repository=repo, cap="100.00")
        summary = await tracker.summary(last_n=10)
        assert summary.remaining_usd == Decimal("90.00")

    async def test_remaining_usd_is_zero_when_overspent(self) -> None:
        """remaining_usd darf nicht negativ sein — Floor bei 0."""
        repo = _make_repository(current_total=Decimal("120.00"))
        tracker = _make_tracker(repository=repo, cap="100.00")
        summary = await tracker.summary(last_n=10)
        assert summary.remaining_usd == Decimal("0")

    async def test_passes_last_n_to_repository(self) -> None:
        """last_n muss an repository.current_month_breakdown durchgereicht werden."""
        repo = _make_repository()
        tracker = _make_tracker(repository=repo)
        await tracker.summary(last_n=5)
        repo.current_month_breakdown.assert_awaited_once_with(5)

    async def test_summary_returns_repository_breakdown_unchanged(self) -> None:
        """Der Service reicht die vom Repository gelieferten Breakdown-Listen
        unverändert durch — Sortierung ist Adapter-Concern."""
        breakdown = CostBreakdown(
            by_model=[
                ModelBreakdown(model="claude-sonnet-4-6", calls=3, cost_usd=Decimal("8.00")),
                ModelBreakdown(model="claude-haiku-4-5", calls=5, cost_usd=Decimal("2.50")),
            ],
            by_feature=[
                FeatureBreakdown(feature="narrative_engine", calls=4, cost_usd=Decimal("5.00")),
            ],
            last_calls=[
                CallEntry(
                    created_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
                    model="claude-sonnet-4-6",
                    feature="narrative_engine",
                    cost_usd=Decimal("1.50"),
                ),
            ],
        )
        repo = _make_repository(breakdown=breakdown)
        tracker = _make_tracker(repository=repo)
        summary = await tracker.summary(last_n=10)
        assert summary.by_model == breakdown.by_model
        assert summary.by_feature == breakdown.by_feature
        assert summary.last_calls == breakdown.last_calls
