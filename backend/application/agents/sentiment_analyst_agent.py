"""SentimentAnalystAgent — reads Fear&Greed from market_sentiment table (D-04 stub).

§0 Iron Rule: numbers come from DB (real data), NOT from LLM memory.

This is a stub for V4-3. V4-4 will add News-RAG to the sentiment analysis,
keeping the same SentimentView output interface.

No LLM call in this stub — the F&G value from DB satisfies the "numbers from Tools"
iron rule immediately.
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa

from backend.domain.schemas.agent_schemas import SentimentView

_logger = logging.getLogger(__name__)

# Regime thresholds — score = (fg_value - 50) / 50
_FEAR_THRESHOLD = -0.2   # score < -0.2 → FEAR
_GREED_THRESHOLD = 0.2   # score > 0.2  → GREED


class SentimentAnalystAgent:
    """Reads real Fear&Greed from market_sentiment table and returns a SentimentView.

    Constructor injection: async SQLAlchemy session.
    No LLM call — DB read satisfies §0 iron rule.
    V4-4 will add News-RAG: only stub body changes, SentimentView interface stays.
    """

    def __init__(self, db_session: Any) -> None:
        self._session = db_session

    async def analyze(self, coin: str) -> SentimentView:
        """Read latest Fear&Greed from market_sentiment and return SentimentView.

        Args:
            coin: Asset identifier (e.g. "BTC"). Used to tag the output.

        Returns:
            SentimentView — always. If DB fails, returns a neutral fallback.
        """
        try:
            result = await self._session.execute(
                sa.text(
                    "SELECT fear_greed, fg_classification "
                    "FROM market_sentiment "
                    "ORDER BY date DESC "
                    "LIMIT 1"
                )
            )
            row = result.first()
            if row is None:
                _logger.warning("market_sentiment table is empty — using neutral fallback")
                return self._fallback(coin, fg_value=50, fg_classification="Neutral (no data)")

            fg_value: int = row.fear_greed
            fg_classification: str = row.fg_classification

            # §0 Iron Rule: normalize F&G to score — NO LLM math
            score: float = (fg_value - 50) / 50

            # Map score to regime by threshold
            if score < _FEAR_THRESHOLD:
                regime = "FEAR"
            elif score > _GREED_THRESHOLD:
                regime = "GREED"
            else:
                regime = "NEUTRAL"

            return SentimentView(
                coin=coin,
                score=score,
                regime=regime,
                news_surprise=None,   # RAG pending V4-4
                veto=False,           # no veto in stub
                reasoning=(
                    f"Fear&Greed index {fg_value} ({fg_classification}). "
                    "News-RAG: V4-4 pending."
                ),
                sources=[],           # RAG pending V4-4
            )

        except Exception as exc:
            _logger.error("SentimentAnalystAgent DB read failed: %s", exc)
            return self._fallback(coin, fg_value=50, fg_classification="Neutral (error)")

    @staticmethod
    def _fallback(coin: str, fg_value: int, fg_classification: str) -> SentimentView:
        """Deterministic fallback when DB is unavailable."""
        score = (fg_value - 50) / 50
        return SentimentView(
            coin=coin,
            score=score,
            regime="NEUTRAL",
            news_surprise=None,
            veto=False,
            reasoning=(
                f"Fallback: DB nicht verfügbar. Fear&Greed index {fg_value} "
                f"({fg_classification}). News-RAG: V4-4 pending."
            ),
            sources=[],
        )
