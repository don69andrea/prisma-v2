"""LLM Smoke Test mit LLM-as-Judge — Weekly-CI gegen echte Anthropic-API.

Prueft die Narrative Engine E2E fuer 3 feste Test-Stocks:
1. Generiert ein Memo via LLMClient (echte API, kein Fixture)
2. Validiert Struktur gegen ResearchMemoSchema (Pydantic)
3. Bewertet Memo-Qualitaet mit einem zweiten Claude-Call (LLM-as-Judge)
4. Exit-Code 1 bei Regression — GitHub Actions erstellt automatisch ein Issue

Keine DB-Abhaengigkeit: Prompts werden mit synthetischen Ranking-Werten
gerendert. Kosten: ~$0.05-0.10 pro Run (Haiku-Modell fuer Judge-Calls).

Ausfuehrung lokal:
    source .venv/bin/activate
    ANTHROPIC_API_KEY=sk-... python scripts/llm_smoke_judge.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from unittest.mock import AsyncMock

import anthropic

from backend.config import get_settings
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.pricing import PRICING
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

MODEL_GENERATE = "claude-sonnet-4-6"
MODEL_JUDGE = "claude-haiku-4-5-20251001"

_TEST_STOCKS: list[dict[str, Any]] = [
    {
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
            "Quality Classic": {"rank": 5, "score": 0.20},
            "Alpha": {"rank": 12, "score": 0.0833},
            "Trend Momentum": {"rank": 8, "score": 0.125},
            "Value Alpha Potential": {"rank": 38, "score": 0.0263},
            "Diversification": {"rank": 6, "score": 0.1667},
        },
        "total_rank": 4,
        "sweet_spot": True,
        "weights": "equal-weighted (0.20 each)",
    },
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Information Technology",
        "country": "US",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "universe_name": "Smoke-Universe",
        "n_stocks": 50,
        "median_rank": 25,
        "top20_threshold": 10,
        "rankings": {
            "Quality Classic": {"rank": 18, "score": 0.0556},
            "Alpha": {"rank": 15, "score": 0.0667},
            "Trend Momentum": {"rank": 7, "score": 0.1429},
            "Value Alpha Potential": {"rank": 42, "score": 0.0238},
            "Diversification": {"rank": 20, "score": 0.05},
        },
        "total_rank": 14,
        "sweet_spot": False,
        "weights": "equal-weighted (0.20 each)",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "sector": "Information Technology",
        "country": "US",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "universe_name": "Smoke-Universe",
        "n_stocks": 50,
        "median_rank": 25,
        "top20_threshold": 10,
        "rankings": {
            "Quality Classic": {"rank": 10, "score": 0.10},
            "Alpha": {"rank": 14, "score": 0.0714},
            "Trend Momentum": {"rank": 6, "score": 0.1667},
            "Value Alpha Potential": {"rank": 3, "score": 0.3333},
            "Diversification": {"rank": 16, "score": 0.0625},
        },
        "total_rank": 7,
        "sweet_spot": False,
        "weights": "equal-weighted (0.20 each)",
    },
]

_JUDGE_SYSTEM = (
    "Du bist ein Qualitaets-Evaluator fuer Aktien-Research-Memos. "
    "Antworte ausschliesslich mit PASS oder FAIL, gefolgt von einem Bindestrich und "
    "einem einzigen Satz auf Deutsch."
)

_JUDGE_USER_TEMPLATE = """Bewerte das folgende Research-Memo auf Qualitaet.

PASS-Kriterien (alle muessen erfuellt sein):
1. one_liner ist aussagekraeftig (mindestens 20 Zeichen, kein Platzhalter)
2. ranking_interpretation ist coherent und mindestens 100 Zeichen lang
3. key_strengths hat mindestens 1 Eintrag
4. key_risks hat mindestens 1 Eintrag
5. confidence ist eines von: high / medium / low
6. Kein offensichtlicher Widerspruch zwischen sweet_spot und confidence

MEMO (JSON):
{memo}

Antworte mit: PASS - <ein Satz> oder FAIL - <ein Satz>"""


async def _generate_memo(
    llm: LLMClient,
    loader: PromptTemplateLoader,
    stock: dict[str, Any],
) -> ResearchMemoSchema:
    system_prompt = loader.render("narrative_system.de.md.j2", {})
    user_prompt = loader.render("narrative_user.de.md.j2", stock)

    response = await llm.messages_create(
        model=MODEL_GENERATE,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
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
        feature="narrative_smoke_judge",
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        raise ValueError(f"Kein tool_use-Block in Anthropic-Response fuer {stock['ticker']}")

    return ResearchMemoSchema.model_validate(tool_block.input)


async def _judge_memo(
    client: anthropic.AsyncAnthropic,
    memo: ResearchMemoSchema,
    ticker: str,
) -> tuple[bool, str]:
    memo_json = json.dumps(memo.model_dump(mode="json"), ensure_ascii=False, indent=2)
    response = await client.messages.create(
        model=MODEL_JUDGE,
        max_tokens=256,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": _JUDGE_USER_TEMPLATE.format(memo=memo_json)}],
    )
    verdict = response.content[0].text.strip()
    passed = verdict.upper().startswith("PASS")
    return passed, verdict


async def main() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("FAIL: ANTHROPIC_API_KEY nicht gesetzt — Abbruch.", file=sys.stderr)
        sys.exit(1)

    raw_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    cost_tracker = AsyncMock()
    cost_tracker.check_cap = AsyncMock()
    cost_tracker.record = AsyncMock()

    llm = LLMClient(
        anthropic=raw_client,
        voyage=None,
        cost_tracker=cost_tracker,
        pricing=PRICING,
    )
    loader = PromptTemplateLoader()

    failures: list[str] = []
    print(f"PRISMA LLM Smoke Judge — {len(_TEST_STOCKS)} Stocks")
    print(f"Generate: {MODEL_GENERATE}  |  Judge: {MODEL_JUDGE}")
    print("-" * 60)

    for stock in _TEST_STOCKS:
        ticker = stock["ticker"]
        try:
            memo = await _generate_memo(llm, loader, stock)
            print(f"[{ticker}] Schema OK — one_liner: {memo.one_liner!r}")
        except Exception as exc:
            msg = f"{ticker}: Generate/Schema fehlgeschlagen — {exc}"
            print(f"[{ticker}] FAIL (generate): {exc}")
            failures.append(msg)
            continue

        passed, verdict = await _judge_memo(raw_client, memo, ticker)
        print(f"[{ticker}] Judge: {verdict}")
        if not passed:
            failures.append(f"{ticker}: LLM-Judge — {verdict}")

    print("-" * 60)
    if failures:
        print(f"SMOKE FAILED ({len(failures)} Fehler):")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)

    print(f"SMOKE PASSED — alle {len(_TEST_STOCKS)} Stocks bestanden")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
