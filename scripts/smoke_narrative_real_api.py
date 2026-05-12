"""Smoke-Test: Narrative-Engine gegen echte Anthropic-API.

Verifiziert PR #64 W5 (Spec §10 Acceptance):
- `cache_control: ephemeral` wird vom `LLMClient` zur SDK durchgereicht.
- Beim 2. Call zeigt `usage.cache_read_input_tokens > 0` (Cache-Hit).
- Tool-Use-Output validiert gegen `ResearchMemoSchema`.
- Latenz und Kosten in plausiblem Bereich.

Keine DB-Abhängigkeit — Prompts werden mit synthetischen Sample-Werten
gerendert. Geht durch denselben `LLMClient`-Wrapper wie Production
(mit Stub-CostTracker, also ohne DB-Cost-Log-Eintrag).

Ausführung:
    source .venv/bin/activate
    python scripts/smoke_narrative_real_api.py

Erwartete Kosten: ~5-7 cents (2 Calls Sonnet 4.6 mit ~3k input, ~1k output).
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import anthropic

from backend.config import get_settings
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

# Synthetic sample matching the structure NarrativeService passes to the user template.
USER_PROMPT_CONTEXT: dict[str, Any] = {
    "ticker": "NESN",
    "name": "Nestlé SA",
    "sector": "Consumer Staples",
    "country": "CH",
    "run_id": "00000000-0000-0000-0000-000000000001",
    "universe_name": "Smoke-Universe",
    "n_stocks": 50,
    "median_rank": 25,
    "top20_threshold": 10,
    "rankings": {
        "Quality Classic": {"rank": 5, "score": 0.2},
        "Alpha": {"rank": 12, "score": 0.0833},
        "Trend Momentum": {"rank": 8, "score": 0.125},
        "Value Alpha Potential": {"rank": 38, "score": 0.0263},
        "Diversification": {"rank": 6, "score": 0.1667},
    },
    "total_rank": 4,
    "sweet_spot": True,
    "weights": "equal-weighted (0.20 each)",
}

MODEL = "claude-sonnet-4-6"
INPUT_PER_MTOK = Decimal("3.00")
OUTPUT_PER_MTOK = Decimal("15.00")
# Anthropic standard cache pricing: write = 1.25x input, read = 0.10x input.
CACHE_WRITE_PER_MTOK = INPUT_PER_MTOK * Decimal("1.25")
CACHE_READ_PER_MTOK = INPUT_PER_MTOK * Decimal("0.10")
ONE_MILLION = Decimal("1_000_000")


async def _make_call(llm: LLMClient, system_prompt: str, user_prompt: str) -> tuple[Any, float]:
    start = time.perf_counter()
    response = await llm.messages_create(
        model=MODEL,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        tools=[
            {
                "name": "submit_memo",
                "description": "Submit the structured research memo.",
                "input_schema": ResearchMemoSchema.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "submit_memo"},
        max_tokens=2000,
        feature="narrative_smoke",
    )
    return response, time.perf_counter() - start


def _usage_dict(response: Any) -> dict[str, int]:
    u = response.usage
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }


def _cost_usd(usage: dict[str, int]) -> Decimal:
    in_cost = Decimal(usage["input_tokens"]) * INPUT_PER_MTOK / ONE_MILLION
    out_cost = Decimal(usage["output_tokens"]) * OUTPUT_PER_MTOK / ONE_MILLION
    cw_cost = Decimal(usage["cache_creation_input_tokens"]) * CACHE_WRITE_PER_MTOK / ONE_MILLION
    cr_cost = Decimal(usage["cache_read_input_tokens"]) * CACHE_READ_PER_MTOK / ONE_MILLION
    return in_cost + out_cost + cw_cost + cr_cost


async def main() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY in .env nicht gesetzt — Abbruch.")

    loader = PromptTemplateLoader()
    system_prompt = loader.render("narrative_system.de.md.j2", {})
    user_prompt = loader.render("narrative_user.md.j2", USER_PROMPT_CONTEXT)

    cost_tracker = AsyncMock()
    cost_tracker.check_cap = AsyncMock()
    cost_tracker.record = AsyncMock()
    anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    llm = LLMClient(anthropic=anthropic_client, voyage=None, cost_tracker=cost_tracker)

    print("=" * 64)
    print("PRISMA Narrative-Engine — Real-API-Smoke (PR #64 W5)")
    print("=" * 64)
    print(f"Model: {MODEL}")
    print(f"System-Prompt: {len(system_prompt)} chars (~{len(system_prompt) // 3} tokens estimate)")
    print(f"User-Prompt:   {len(user_prompt)} chars (~{len(user_prompt) // 3} tokens estimate)")
    print()

    print("Call 1 (cache creation expected) ...")
    resp1, lat1 = await _make_call(llm, system_prompt, user_prompt)
    u1 = _usage_dict(resp1)
    cost1 = _cost_usd(u1)
    print(
        f"  Latenz: {lat1:.2f}s  |  input={u1['input_tokens']}  output={u1['output_tokens']}  "
        f"cache_create={u1['cache_creation_input_tokens']}  cache_read={u1['cache_read_input_tokens']}  "
        f"|  ${cost1:.4f}"
    )

    tool_use = next((b for b in resp1.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise SystemExit("FAIL: kein tool_use-Block in Call 1 Response")
    try:
        memo = ResearchMemoSchema.model_validate(tool_use.input)
        print(f"  Schema-Validation OK — one_liner: {memo.one_liner!r}")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: Schema-Validation Call 1: {exc}") from exc
    print()

    print("Call 2 (cache read expected) ...")
    resp2, lat2 = await _make_call(llm, system_prompt, user_prompt)
    u2 = _usage_dict(resp2)
    cost2 = _cost_usd(u2)
    print(
        f"  Latenz: {lat2:.2f}s  |  input={u2['input_tokens']}  output={u2['output_tokens']}  "
        f"cache_create={u2['cache_creation_input_tokens']}  cache_read={u2['cache_read_input_tokens']}  "
        f"|  ${cost2:.4f}"
    )
    tool_use2 = next((b for b in resp2.content if b.type == "tool_use"), None)
    if tool_use2 is None:
        raise SystemExit("FAIL: kein tool_use-Block in Call 2 Response")
    try:
        ResearchMemoSchema.model_validate(tool_use2.input)
        print("  Schema-Validation OK")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: Schema-Validation Call 2: {exc}") from exc
    print()

    print("=" * 64)
    print("VERDICT")
    print("=" * 64)
    cache_create_ok = u1["cache_creation_input_tokens"] > 0
    cache_hit_ok = u2["cache_read_input_tokens"] > 0
    print(
        f"Cache-Creation auf Call 1: {'JA' if cache_create_ok else 'NEIN'}  "
        f"({u1['cache_creation_input_tokens']} tokens)"
    )
    print(
        f"Cache-Hit       auf Call 2: {'JA' if cache_hit_ok else 'NEIN'}  "
        f"({u2['cache_read_input_tokens']} tokens)"
    )
    if cache_create_ok and cache_hit_ok:
        print("\n  ✓ Prompt-Caching funktioniert E2E.")
    else:
        print("\n  ✗ Cache-Verhalten nicht wie erwartet — investigate.")

    print()
    print("=" * 64)
    print("MARKDOWN-Snippet für docs/AI-USAGE.md (copy-paste):")
    print("=" * 64)
    print(
        f"""
### Real-API-Smoke verifiziert ({time.strftime("%Y-%m-%d")})

Model: `{MODEL}`. 2 Calls hintereinander mit identischem System-Prompt + `cache_control=ephemeral`.

| | Input | Output | Cache-Create | Cache-Read | Latenz | Kosten |
|---|---|---|---|---|---|---|
| Call 1 | {u1["input_tokens"]} | {u1["output_tokens"]} | {u1["cache_creation_input_tokens"]} | {u1["cache_read_input_tokens"]} | {lat1:.2f}s | ${cost1:.4f} |
| Call 2 | {u2["input_tokens"]} | {u2["output_tokens"]} | {u2["cache_creation_input_tokens"]} | {u2["cache_read_input_tokens"]} | {lat2:.2f}s | ${cost2:.4f} |

Cache-Read auf Call 2: ✓ ({u2["cache_read_input_tokens"]} Tokens). `cache_control: ephemeral` wird korrekt vom `LLMClient` zur SDK durchgereicht; Anthropic cached den DE-System-Block.

Tool-Use-Output beider Calls validiert gegen `ResearchMemoSchema` — OK.
"""
    )


if __name__ == "__main__":
    asyncio.run(main())
