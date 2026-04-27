"""Unit-Tests für LLMClient — wraps Anthropic + Voyage SDKs mit Cost-Tracking.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §4.

Tests injizieren Fake-SDK-Clients und Fake-CostTracker; kein Live-API-Call,
keine echte DB-Verbindung.
"""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from backend.domain.errors import BudgetCapExceeded
from backend.infrastructure.llm.client import LLMClient

pytestmark = pytest.mark.unit


def _fake_anthropic_response(
    *, input_tokens: int = 312, output_tokens: int = 87, msg_id: str = "msg_test"
) -> Any:
    """Imitiert die Felder, die LLMClient aus einer Anthropic-Message liest."""
    return SimpleNamespace(
        id=msg_id,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        content=[SimpleNamespace(type="text", text="hello")],
    )


def _fake_voyage_response(*, total_tokens: int = 42, dim: int = 4) -> Any:
    """Imitiert die Felder, die LLMClient aus einer Voyage-Embeddings-Response liest."""
    return SimpleNamespace(
        embeddings=[[0.1] * dim, [0.2] * dim],
        total_tokens=total_tokens,
    )


def _build_client(
    *,
    anthropic_response: Any = None,
    anthropic_raises: BaseException | None = None,
    voyage_response: Any = None,
    voyage_raises: BaseException | None = None,
    check_cap_raises: BaseException | None = None,
) -> tuple[LLMClient, Any, Any, Any]:
    """Konstruiert LLMClient mit Fakes für alle drei Dependencies.

    Returns: (client, anthropic_mock, voyage_mock, cost_tracker_mock)
    """
    anthropic = Mock()
    if anthropic_raises is not None:
        anthropic.messages.create = AsyncMock(side_effect=anthropic_raises)
    else:
        anthropic.messages.create = AsyncMock(
            return_value=anthropic_response or _fake_anthropic_response()
        )

    voyage = Mock()
    if voyage_raises is not None:
        voyage.embed = Mock(side_effect=voyage_raises)
    else:
        voyage.embed = Mock(return_value=voyage_response or _fake_voyage_response())

    tracker = Mock()
    if check_cap_raises is not None:
        tracker.check_cap = AsyncMock(side_effect=check_cap_raises)
    else:
        tracker.check_cap = AsyncMock()
    tracker.record = AsyncMock()

    client = LLMClient(
        anthropic=anthropic,
        voyage=voyage,
        cost_tracker=tracker,
    )
    return client, anthropic, voyage, tracker


class TestMessagesCreate:
    async def test_calls_check_cap_before_sdk(self) -> None:
        client, anthropic, _, tracker = _build_client()
        await client.messages_create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=1024,
            feature="narrative_engine",
        )
        tracker.check_cap.assert_awaited_once()
        estimated = tracker.check_cap.await_args.kwargs["estimated_usd"]
        assert estimated > Decimal("0"), "estimated_usd should be positive"

    async def test_does_not_call_sdk_when_cap_exceeded(self) -> None:
        cap_exc = BudgetCapExceeded(
            current_usd=Decimal("99.00"),
            attempted_usd=Decimal("1.00"),
            cap_usd=Decimal("100.00"),
        )
        client, anthropic, _, tracker = _build_client(check_cap_raises=cap_exc)
        with pytest.raises(BudgetCapExceeded):
            await client.messages_create(
                model="claude-sonnet-4-6",
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=1024,
                feature="narrative_engine",
            )
        anthropic.messages.create.assert_not_called()
        tracker.record.assert_not_called()

    async def test_records_actual_usage_after_sdk(self) -> None:
        client, _, _, tracker = _build_client(
            anthropic_response=_fake_anthropic_response(
                input_tokens=312,
                output_tokens=87,
                msg_id="msg_real_id",
            ),
        )
        await client.messages_create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=1024,
            feature="narrative_engine",
        )
        tracker.record.assert_awaited_once()
        rec = tracker.record.await_args.kwargs
        assert rec["provider"] == "anthropic"
        assert rec["model"] == "claude-sonnet-4-6"
        assert rec["feature"] == "narrative_engine"
        assert rec["input_tokens"] == 312
        assert rec["output_tokens"] == 87
        assert rec["request_id"] == "msg_real_id"

    async def test_does_not_record_when_sdk_raises(self) -> None:
        client, _, _, tracker = _build_client(
            anthropic_raises=RuntimeError("API down"),
        )
        with pytest.raises(RuntimeError):
            await client.messages_create(
                model="claude-sonnet-4-6",
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=1024,
                feature="narrative_engine",
            )
        tracker.record.assert_not_called()

    async def test_estimates_input_tokens_via_chars_per_token_constant(self) -> None:
        # 4000 chars input + 1024 max_tokens output, Sonnet pricing $3/$15;
        # chars/3-Estimator → ~1333 in-Tokens.
        # 1333 × 3/1M + 1024 × 15/1M = 0.004 + 0.01536 ≈ 0.01936
        client, _, _, tracker = _build_client()
        await client.messages_create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "x" * 4000}],
            max_tokens=1024,
            feature="test",
        )
        estimated = tracker.check_cap.await_args.kwargs["estimated_usd"]
        assert Decimal("0.015") < estimated < Decimal("0.025")

    async def test_estimation_includes_system_prompt_chars(self) -> None:
        # System prompt mit 400 Zeichen sollte 100 Tokens zur Estimation beitragen
        client, _, _, tracker = _build_client()
        await client.messages_create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "x" * 400}],
            max_tokens=100,
            feature="test",
            system="y" * 400,
        )
        estimated_with = tracker.check_cap.await_args.kwargs["estimated_usd"]

        # Vergleich ohne system
        client2, _, _, tracker2 = _build_client()
        await client2.messages_create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "x" * 400}],
            max_tokens=100,
            feature="test",
        )
        estimated_without = tracker2.check_cap.await_args.kwargs["estimated_usd"]
        assert estimated_with > estimated_without

    async def test_passes_kwargs_to_sdk_but_not_feature(self) -> None:
        client, anthropic, _, _ = _build_client()
        await client.messages_create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1024,
            feature="narrative_engine",
            system="You are helpful",
            temperature=0.7,
        )
        sdk_call = anthropic.messages.create.await_args.kwargs
        assert sdk_call["model"] == "claude-sonnet-4-6"
        assert sdk_call["max_tokens"] == 1024
        assert sdk_call["system"] == "You are helpful"
        assert sdk_call["temperature"] == 0.7
        # `feature` ist nur intern fürs Audit-Log — darf nicht ans SDK weitergereicht werden
        assert "feature" not in sdk_call


class TestEmbed:
    async def test_calls_check_cap_before_sdk(self) -> None:
        client, _, _, tracker = _build_client()
        await client.embed(
            model="voyage-3-large",
            texts=["hello world"],
            feature="rag_ingestion",
        )
        tracker.check_cap.assert_awaited_once()

    async def test_records_usage_after_sdk(self) -> None:
        client, _, _, tracker = _build_client(
            voyage_response=_fake_voyage_response(total_tokens=42, dim=4),
        )
        result = await client.embed(
            model="voyage-3-large",
            texts=["hello", "world"],
            feature="rag_ingestion",
        )
        # Embeddings werden weitergereicht
        assert result == [[0.1, 0.1, 0.1, 0.1], [0.2, 0.2, 0.2, 0.2]]
        # Record wurde mit Voyage-Provider aufgerufen
        rec = tracker.record.await_args.kwargs
        assert rec["provider"] == "voyage"
        assert rec["model"] == "voyage-3-large"
        assert rec["feature"] == "rag_ingestion"
        assert rec["input_tokens"] == 42
        assert rec["output_tokens"] == 0  # Embeddings haben keinen Output

    async def test_does_not_call_sdk_when_cap_exceeded(self) -> None:
        cap_exc = BudgetCapExceeded(
            current_usd=Decimal("99.00"),
            attempted_usd=Decimal("1.00"),
            cap_usd=Decimal("100.00"),
        )
        client, _, voyage, tracker = _build_client(check_cap_raises=cap_exc)
        with pytest.raises(BudgetCapExceeded):
            await client.embed(
                model="voyage-3-large",
                texts=["hello"],
                feature="rag_ingestion",
            )
        voyage.embed.assert_not_called()
        tracker.record.assert_not_called()
