"""W3-M-06 Regression — SentimentAnalystAgent DB-NULL-Guard für fear_greed.

Audit-Befund W3-M-06 (Medium): Ist die Spalte `fear_greed` in market_sentiment
NULL, wurde `fg_value=None` gesetzt und `_compute_score((None-50)/50)` warf einen
ungefangenen TypeError → 500, obwohl der Docstring (D-09) eine Fallback-Kette
garantiert.

Diese Tests beweisen: `analyze` crasht NICHT bei fear_greed=None, sondern liefert
einen neutralen/Fallback-SentimentView (score 0.0, regime NEUTRAL). Kein Netzwerk /
echter LLM-Call — alle Dependencies gemockt.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _build_agent(
    fg_value: Any,
    fg_classification: Any = "Neutral",
    num_articles: int = 0,
    votes_positive: int = 0,
    votes_negative: int = 0,
) -> Any:
    """Build SentimentAnalystAgent with fully mocked dependencies (no I/O)."""
    from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.fear_greed = fg_value
    mock_row.fg_classification = fg_classification
    mock_result.first.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_retrieval = AsyncMock()
    chunks = []
    for i in range(num_articles):
        chunk = MagicMock()
        chunk.url = f"https://cryptopanic.com/news/{i}/btc-article"
        chunk.content = f"news chunk {i}"
        chunk.metadata = {
            "source": "CRYPTOPANIC",
            "tickers": ["BTC"],
            "votes_positive": votes_positive,
            "votes_negative": votes_negative,
        }
        chunks.append(chunk)
    mock_retrieval.retrieve = AsyncMock(return_value=chunks)

    mock_llm = AsyncMock()
    mock_content = MagicMock()
    mock_content.text = '{"news_surprise": false, "reasoning": "No significant events."}'
    mock_llm.messages_create = AsyncMock(return_value=MagicMock(content=[mock_content]))

    mock_prompts = MagicMock()
    mock_prompts.render = MagicMock(return_value="rendered prompt")

    return SentimentAnalystAgent(
        db_session=mock_session,
        news_retrieval_service=mock_retrieval,
        llm_client=mock_llm,
        prompt_loader=mock_prompts,
    )


@pytest.mark.asyncio
async def test_fear_greed_null_does_not_crash_empty_corpus() -> None:
    """W3-M-06: fear_greed=NULL + leeres Corpus → Fallback, kein TypeError/500."""
    agent = _build_agent(fg_value=None, num_articles=0)

    result = await agent.analyze("BTC")

    # Neutraler Default fg=50 → score 0.0 → NEUTRAL, kein Crash
    assert result.score == 0.0
    assert result.regime == "NEUTRAL"
    assert result.veto is False
    assert result.news_surprise is None
    assert result.coin == "BTC"


@pytest.mark.asyncio
async def test_fear_greed_null_does_not_crash_with_articles() -> None:
    """W3-M-06: fear_greed=NULL trifft _compute_score direkt (>=5 Chunks) → kein Crash."""
    # >= _MIN_ARTICLES_FOR_VOTE_RATIO Chunks aktivieren die Blend-Formel, sodass
    # _compute_score mit fg_norm rechnet — genau der zuvor crashende Pfad.
    agent = _build_agent(
        fg_value=None,
        num_articles=5,
        votes_positive=0,
        votes_negative=0,
    )

    result = await agent.analyze("BTC")

    # Blend: 0.7 * 0 (ausgeglichene Votes) + 0.3 * (50-50)/50 = 0.0
    assert result.score == 0.0
    assert result.regime == "NEUTRAL"
    assert result.veto is False


@pytest.mark.asyncio
async def test_fg_classification_null_does_not_crash() -> None:
    """W3-M-06: Auch NULL-fg_classification liefert einen gültigen SentimentView."""
    agent = _build_agent(fg_value=None, fg_classification=None, num_articles=0)

    result = await agent.analyze("BTC")

    assert result.score == 0.0
    assert result.regime == "NEUTRAL"
    assert isinstance(result.reasoning, str)
    assert result.reasoning != ""
