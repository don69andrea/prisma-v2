"""RED test stubs — SentimentAnalystAgent score formula + veto truth table (REQ-4-07).

Tests D-03 blend formula, fallback, regime boundaries, and D-05 veto truth table.

Status: RED until SentimentAnalystAgent is upgraded in plan 04-05 to implement
the V4-4 RAG + vote-ratio score formula.

Constants (as specified in 04-CONTEXT.md D-03/D-05):
  _VETO_SCORE_THRESHOLD = -0.3
  _FEAR_THRESHOLD       = -0.2
  _MIN_ARTICLES_FOR_VOTE_RATIO = 5
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Exact threshold constants as specified (D-03, D-05)
# ---------------------------------------------------------------------------
_VETO_SCORE_THRESHOLD = -0.3
_FEAR_THRESHOLD = -0.2
_MIN_ARTICLES_FOR_VOTE_RATIO = 5


# ---------------------------------------------------------------------------
# Agent builder helper
# ---------------------------------------------------------------------------


def _build_agent(
    fg_value: int,
    fg_classification: str = "Neutral",
    news_chunks: list[Any] | None = None,
    votes_positive: int = 0,
    votes_negative: int = 0,
    num_articles: int = 0,
) -> Any:
    """Build V4-4 SentimentAnalystAgent with mocked dependencies.

    Mocks:
    - db_session returning fg_value + fg_classification from market_sentiment
    - news_retrieval_service returning num_articles worth of chunks with given votes
    - llm_client returning news_surprise=False by default (deterministic formula tests)
    """
    from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent

    # Mock DB session (Fear&Greed)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.fear_greed = fg_value
    mock_row.fg_classification = fg_classification
    mock_result.first.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock news retrieval service — returns chunks with vote metadata
    mock_retrieval = AsyncMock()
    if news_chunks is not None:
        mock_retrieval.retrieve = AsyncMock(return_value=news_chunks)
    else:
        # Build synthetic chunks with votes embedded in metadata
        chunks = []
        for i in range(num_articles):
            chunk = MagicMock()
            chunk.url = f"https://cryptopanic.com/news/{i}/btc-article"
            chunk.metadata = {
                "source": "CRYPTOPANIC",
                "tickers": ["BTC"],
                "votes_positive": votes_positive // max(1, num_articles),
                "votes_negative": votes_negative // max(1, num_articles),
            }
            chunks.append(chunk)
        mock_retrieval.retrieve = AsyncMock(return_value=chunks)

    # Mock LLM client — returns news_surprise=False by default (pure formula testing)
    mock_llm = AsyncMock()
    mock_content = MagicMock()
    mock_content.text = '{"news_surprise": false, "reasoning": "No significant new events."}'
    mock_llm.messages_create = AsyncMock(
        return_value=MagicMock(content=[mock_content])
    )

    # Mock prompt loader
    mock_prompts = MagicMock()
    mock_prompts.render = MagicMock(return_value="rendered sentiment prompt")

    return SentimentAnalystAgent(
        db_session=mock_session,
        news_retrieval_service=mock_retrieval,
        llm_client=mock_llm,
        prompt_loader=mock_prompts,
    )


# ---------------------------------------------------------------------------
# D-03: Blend formula tests (>= _MIN_ARTICLES_FOR_VOTE_RATIO articles)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "votes_positive,votes_negative,fg_value,expected_score",
    [
        # score_news = (pos-neg)/max(1,pos+neg); score = 0.7*score_news + 0.3*fg_norm
        # fg_norm = (fg-50)/50
        (10, 0, 50, 0.7 * (10 - 0) / max(1, 10) + 0.3 * (50 - 50) / 50),  # all positive votes, neutral F&G
        (0, 10, 50, 0.7 * (0 - 10) / max(1, 10) + 0.3 * (50 - 50) / 50),  # all negative votes, neutral F&G
        (7, 3, 75, 0.7 * (7 - 3) / max(1, 7 + 3) + 0.3 * (75 - 50) / 50),  # mixed votes, greed F&G
        (3, 7, 25, 0.7 * (3 - 7) / max(1, 3 + 7) + 0.3 * (25 - 50) / 50),  # mixed negative, fear F&G
        (5, 5, 50, 0.7 * (5 - 5) / max(1, 5 + 5) + 0.3 * (50 - 50) / 50),  # balanced votes, neutral
    ],
)
@pytest.mark.asyncio
async def test_d03_blend_formula_with_sufficient_articles(
    votes_positive: int,
    votes_negative: int,
    fg_value: int,
    expected_score: float,
) -> None:
    """D-03: score = 0.7*(pos-neg)/max(1,pos+neg) + 0.3*(fg-50)/50 when >= 5 articles.

    Uses _MIN_ARTICLES_FOR_VOTE_RATIO = 5 as the threshold.
    """
    agent = _build_agent(
        fg_value=fg_value,
        num_articles=_MIN_ARTICLES_FOR_VOTE_RATIO,
        votes_positive=votes_positive,
        votes_negative=votes_negative,
    )
    result = await agent.analyze("BTC")
    assert abs(result.score - expected_score) < 1e-9, (
        f"score={result.score!r} != expected={expected_score!r} "
        f"(pos={votes_positive}, neg={votes_negative}, fg={fg_value})"
    )


# ---------------------------------------------------------------------------
# D-03: Fallback formula (< _MIN_ARTICLES_FOR_VOTE_RATIO articles)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fg_value,expected_score",
    [
        (0, (0 - 50) / 50),     # extreme fear → -1.0
        (50, (50 - 50) / 50),   # neutral → 0.0
        (100, (100 - 50) / 50), # extreme greed → 1.0
        (25, (25 - 50) / 50),   # fear → -0.5
        (75, (75 - 50) / 50),   # greed → 0.5
    ],
)
@pytest.mark.asyncio
async def test_d03_fallback_fg_only_when_insufficient_articles(
    fg_value: int,
    expected_score: float,
) -> None:
    """D-03 Fallback: score = fg_norm = (fg-50)/50 when < 5 articles available."""
    # num_articles < _MIN_ARTICLES_FOR_VOTE_RATIO triggers fallback
    agent = _build_agent(
        fg_value=fg_value,
        num_articles=_MIN_ARTICLES_FOR_VOTE_RATIO - 1,  # = 4 articles
        votes_positive=0,
        votes_negative=0,
    )
    result = await agent.analyze("BTC")
    assert abs(result.score - expected_score) < 1e-9, (
        f"Fallback score={result.score!r} != fg_norm={expected_score!r} (fg={fg_value})"
    )


# ---------------------------------------------------------------------------
# D-03: Regime boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fg_value,expected_regime",
    [
        # _FEAR_THRESHOLD = -0.2: score < -0.2 → FEAR
        (40, "FEAR"),    # score = (40-50)/50 = -0.2 → boundary (FEAR or NEUTRAL? test boundary)
        (30, "FEAR"),    # score = (30-50)/50 = -0.4 → clearly FEAR
        (60, "GREED"),   # score = (60-50)/50 = 0.2 → boundary (GREED or NEUTRAL?)
        (70, "GREED"),   # score = (70-50)/50 = 0.4 → clearly GREED
        (50, "NEUTRAL"), # score = 0.0 → NEUTRAL
    ],
)
@pytest.mark.asyncio
async def test_regime_boundaries(fg_value: int, expected_regime: str) -> None:
    """D-03: regime boundaries at _FEAR_THRESHOLD=-0.2 and _GREED_THRESHOLD=+0.2."""
    # Use fallback mode (< 5 articles) so score = pure fg_norm
    agent = _build_agent(
        fg_value=fg_value,
        num_articles=0,  # no articles → pure F&G fallback
    )
    result = await agent.analyze("BTC")
    assert result.regime == expected_regime, (
        f"fg={fg_value} → score={(fg_value - 50) / 50:.3f} expected regime={expected_regime!r}, "
        f"got {result.regime!r}"
    )


# ---------------------------------------------------------------------------
# D-05: Veto truth table — all 8 combinations
# Veto = (regime == "FEAR") AND (news_surprise == True) AND (score < _VETO_SCORE_THRESHOLD)
# _VETO_SCORE_THRESHOLD = -0.3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "is_fear_regime,news_surprise,score_below_threshold,expected_veto",
    [
        # All 8 combinations of (regime=FEAR, news_surprise=True, score<-0.3)
        (True,  True,  True,  True),   # ALL conditions met → veto=True
        (True,  True,  False, False),  # score >= -0.3 → no veto
        (True,  False, True,  False),  # news_surprise=False → no veto
        (True,  False, False, False),  # fear + no surprise + good score → no veto
        (False, True,  True,  False),  # not fear regime → no veto
        (False, True,  False, False),  # not fear, not below threshold → no veto
        (False, False, True,  False),  # not fear, no surprise → no veto
        (False, False, False, False),  # no conditions met → no veto
    ],
)
@pytest.mark.asyncio
async def test_d05_veto_truth_table(
    is_fear_regime: bool,
    news_surprise: bool,
    score_below_threshold: bool,
    expected_veto: bool,
) -> None:
    """D-05: veto = (regime==FEAR) AND (news_surprise==True) AND (score < _VETO_SCORE_THRESHOLD=-0.3).

    Tests all 8 combinations (C-01 truth table).
    """
    # Determine fg_value to produce the desired regime
    # FEAR: fg < 40 (score < -0.2), not FEAR: fg >= 40
    if is_fear_regime:
        # score = (fg-50)/50 < -0.2  → fg < 40
        fg_value = 30  # score = -0.4, regime = FEAR
    else:
        fg_value = 60  # score = 0.2, regime = NEUTRAL/GREED

    # Determine votes to push score below/above _VETO_SCORE_THRESHOLD=-0.3
    # Use >=5 articles to activate blend formula
    if score_below_threshold:
        # blend score < -0.3: use very negative votes + fear F&G
        votes_positive = 0
        votes_negative = 10
        num_articles = _MIN_ARTICLES_FOR_VOTE_RATIO
    else:
        # score >= -0.3: use balanced or positive votes
        votes_positive = 5
        votes_negative = 0
        num_articles = _MIN_ARTICLES_FOR_VOTE_RATIO

    # Mock LLM to return specific news_surprise value
    from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.fear_greed = fg_value
    mock_row.fg_classification = "Fear" if is_fear_regime else "Greed"
    mock_result.first.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_retrieval = AsyncMock()
    chunks = []
    for i in range(num_articles):
        chunk = MagicMock()
        chunk.url = f"https://cryptopanic.com/news/{i}/btc-article"
        chunk.metadata = {
            "source": "CRYPTOPANIC",
            "tickers": ["BTC"],
            "votes_positive": votes_positive // max(1, num_articles),
            "votes_negative": votes_negative // max(1, num_articles),
        }
        chunks.append(chunk)
    mock_retrieval.retrieve = AsyncMock(return_value=chunks)

    # LLM returns the specific news_surprise value for this test case
    mock_llm = AsyncMock()
    mock_content = MagicMock()
    ns_str = "true" if news_surprise else "false"
    mock_content.text = f'{{"news_surprise": {ns_str}, "reasoning": "Test reasoning."}}'
    mock_llm.messages_create = AsyncMock(
        return_value=MagicMock(content=[mock_content])
    )

    mock_prompts = MagicMock()
    mock_prompts.render = MagicMock(return_value="rendered prompt")

    agent = SentimentAnalystAgent(
        db_session=mock_session,
        news_retrieval_service=mock_retrieval,
        llm_client=mock_llm,
        prompt_loader=mock_prompts,
    )
    result = await agent.analyze("BTC")
    assert result.veto == expected_veto, (
        f"is_fear={is_fear_regime}, news_surprise={news_surprise}, "
        f"score_below={score_below_threshold}: "
        f"expected veto={expected_veto}, got veto={result.veto} "
        f"(score={result.score:.3f}, regime={result.regime})"
    )
