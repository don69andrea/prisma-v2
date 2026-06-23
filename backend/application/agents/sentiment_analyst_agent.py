"""SentimentAnalystAgent — RAG-News + Fear&Greed → SentimentView (V4-4).

§0 Iron Rule: score, regime und veto werden AUSSCHLIESSLICH deterministisch
in Python berechnet — nie vom LLM. Das LLM liefert nur news_surprise: bool
+ reasoning: str (D-04, SentimentLLMOutput).

D-03 Score-Formel (deterministisch):
  - Wenn >= _MIN_ARTICLES_FOR_VOTE_RATIO Artikel mit Votes verfügbar:
      score = 0.7*(pos-neg)/max(1,pos+neg) + 0.3*(fg-50)/50,  clamp[-1,1]
  - Sonst (< 5 Artikel):
      score = (fg-50)/50  (reiner F&G-Fallback)

D-05 Veto-Regel (deterministisch, exakt 8 Kombinationen):
  veto = (regime == "FEAR") AND (news_surprise is True) AND (score < -0.3)
  Alle anderen 7 Kombinationen → veto = False

D-09 Fallback-Kette:
  - Leeres/altes Corpus (Retrieval gibt [] zurück) → F&G-Fallback, news_surprise=None, veto=False
  - LLM-Fehler → news_surprise=None, deterministischer Score bleibt erhalten, veto=False

C-01 Signatur: analyze(coin, _context={}) — zweites Argument wird ignoriert,
in der Body nie referenziert (kein Mutable-Default-Seiteneffekt).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import ValidationError

from backend.application.services.news_retrieval_service import NewsRetrievalService
from backend.domain.schemas.agent_schemas import SentimentLLMOutput, SentimentView
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

# Regime-Schwellenwerte — deterministisch, nie vom LLM
_FEAR_THRESHOLD = -0.2  # score < -0.2  → FEAR
_GREED_THRESHOLD = 0.2  # score > +0.2  → GREED

# V4-4 Veto + Score-Blend-Schwellen
_VETO_SCORE_THRESHOLD = -0.3  # score < -0.3 UND FEAR UND news_surprise → veto
_MIN_ARTICLES_FOR_VOTE_RATIO = 5  # Mindestanzahl Chunks für D-03-Blend-Formel

# LLM-Modell (Haiku — schnell, günstig, Projekt-Konvention)
_MODEL = "claude-haiku-4-5-20251001"

# Prompt-Template-Name
_PROMPT_TEMPLATE = "sentiment_analyst.de.md.j2"

# RAG-Retrieval: k Chunks pro Coin, 7-Tage TTL (D-02)
_RAG_K = 5
_RAG_TTL_DAYS = 7


def _compute_score(
    chunks: list[Any],
    fg_value: int,
) -> tuple[float, Literal["FEAR", "NEUTRAL", "GREED"]]:
    """Deterministisch Score + Regime aus Chunks + Fear&Greed berechnen (D-03).

    §0 Iron Rule: Diese Funktion ist reines Python — kein LLM-Aufruf.

    Args:
        chunks: NewsRetrievalResult-Objekte mit .metadata["votes_positive/negative"].
        fg_value: Fear&Greed Index (0–100).

    Returns:
        (score, regime) — score clamp[-1,1], regime FEAR/NEUTRAL/GREED.
    """
    fg_norm: float = (fg_value - 50) / 50  # → [-1, 1]

    if len(chunks) >= _MIN_ARTICLES_FOR_VOTE_RATIO:
        # D-03 Blend-Formel: 0.7 * vote-ratio + 0.3 * fg-Norm
        pos_total = sum(c.metadata.get("votes_positive", 0) for c in chunks)
        neg_total = sum(c.metadata.get("votes_negative", 0) for c in chunks)
        score_news: float = (pos_total - neg_total) / max(1, pos_total + neg_total)
        raw_score: float = 0.7 * score_news + 0.3 * fg_norm
        # Clamp [-1, 1] (T-4-04: vote-stuffing guard)
        score: float = max(-1.0, min(1.0, raw_score))
    else:
        # Fallback: reiner F&G-Norm-Score
        score = fg_norm

    # Regime-Mapping (Grenzen inklusive: score <= -0.2 → FEAR, >= +0.2 → GREED)
    regime: Literal["FEAR", "NEUTRAL", "GREED"]
    if score <= _FEAR_THRESHOLD:
        regime = "FEAR"
    elif score >= _GREED_THRESHOLD:
        regime = "GREED"
    else:
        regime = "NEUTRAL"

    return score, regime


class SentimentAnalystAgent:
    """V4-4 SentimentAnalystAgent — RAG-Retrieval + deterministischer Score + LLM news_surprise.

    Konstruktor-Injection (D-07 / Pattern 2):
      db_session              — async SQLAlchemy Session für Fear&Greed-Abfrage
      news_retrieval_service  — NewsRetrievalService für HNSW-Retrieval
      llm_client              — LLMClient für news_surprise-Abfrage
      prompt_loader           — PromptTemplateLoader (Jinja2, StrictUndefined)

    §0 Iron Rule: LLM gibt AUSSCHLIESSLICH news_surprise: bool + reasoning: str.
    Score, regime, veto werden nach dem LLM-Aufruf deterministisch berechnet.
    """

    def __init__(
        self,
        db_session: Any,
        news_retrieval_service: NewsRetrievalService,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
    ) -> None:
        self._session = db_session
        self._retrieval = news_retrieval_service
        self._llm = llm_client
        self._prompts = prompt_loader

    async def analyze(self, coin: str, _context: dict = {}) -> SentimentView:  # noqa: B006
        """RAG + D-03-Score + LLM news_surprise + D-05-Veto → SentimentView.

        C-01: zweites Argument _context wird akzeptiert aber nie im Body referenziert.
        SignalDirector ruft analyze(coin, {}) auf — Kompatibilität bleibt erhalten.

        Args:
            coin: Asset-Ticker (z.B. "BTC").
            _context: Wird ignoriert. Nur für Signatur-Kompatibilität (C-01).

        Returns:
            SentimentView — immer. Bei DB-Fehler oder leerem Corpus: F&G-Fallback.
        """
        # 1) Fear&Greed aus market_sentiment lesen
        try:
            db_result = await self._session.execute(
                sa.text(
                    "SELECT fear_greed, fg_classification "
                    "FROM market_sentiment "
                    "ORDER BY date DESC "
                    "LIMIT 1"
                )
            )
            row = db_result.first()
            if row is None:
                _logger.warning("market_sentiment leer — F&G-Fallback (fg=50)")
                return self._fallback(coin, fg_value=50, fg_classification="Neutral (keine Daten)")

            fg_value: int = row.fear_greed
            fg_classification: str = row.fg_classification

        except Exception as exc:
            _logger.error("DB-Lesefehler in SentimentAnalystAgent: %s", exc)
            return self._fallback(coin, fg_value=50, fg_classification="Neutral (DB-Fehler)")

        # 2) RAG-Retrieval: Chunks via HNSW abrufen (max_age_days via Retrieval-Service)
        try:
            results = await self._retrieval.retrieve(
                query=f"{coin} crypto sentiment news",
                k=_RAG_K,
                ticker=coin,
            )
        except Exception as exc:
            _logger.warning("RAG-Retrieval fehlgeschlagen für %s: %s — F&G-Fallback", coin, exc)
            results = []

        # D-09 Fallback: Corpus leer → F&G-Fallback, news_surprise=None, veto=False
        if not results:
            _logger.info("Leeres RAG-Corpus für %s — F&G-Fallback", coin)
            return self._fallback(coin, fg_value=fg_value, fg_classification=fg_classification)

        # 3) Deterministischer Score + Regime (§0 Iron Rule — kein LLM-Eingriff)
        score, regime = _compute_score(chunks=results, fg_value=fg_value)

        # 4) LLM: nur news_surprise + reasoning (D-04)
        news_surprise: bool | None = None
        reasoning: str = ""
        try:
            prompt_text = self._prompts.render(
                _PROMPT_TEMPLATE,
                {
                    "coin": coin,
                    "fg_value": fg_value,
                    "fg_classification": fg_classification,
                    "rag_chunks": [r.content for r in results],
                    "n_chunks": len(results),
                },
            )
            llm_response = await self._llm.messages_create(
                model=_MODEL,
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=256,
                feature="sentiment_analyst",
            )
            raw_text: str = llm_response.content[0].text
            # JSON aus Markdown-Code-Block extrahieren falls vorhanden
            if "```" in raw_text:
                raw_text = raw_text.split("```")[-2].strip()
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()
            llm_json = json.loads(raw_text)
            llm_out = SentimentLLMOutput.model_validate(llm_json)
            news_surprise = llm_out.news_surprise
            reasoning = llm_out.reasoning
        except (ValidationError, Exception) as exc:
            # D-09 LLM-Fallback: news_surprise=None, Score bleibt deterministisch, veto=False
            _logger.warning("LLM-Aufruf für %s fehlgeschlagen: %s — news_surprise=None", coin, exc)
            news_surprise = None
            reasoning = f"Fear&Greed index {fg_value} ({fg_classification}). LLM nicht verfügbar."

        # 5) D-05 Veto-Regel (deterministisch, exakt 8 Kombinationen)
        # veto = True NUR wenn: regime=="FEAR" AND news_surprise is True AND score < -0.3
        veto: bool = regime == "FEAR" and news_surprise is True and score < _VETO_SCORE_THRESHOLD

        # 6) Sources = URLs der abgerufenen Chunks (D-07 RAG-Nachweis)
        sources: list[str] = [r.url for r in results]

        # 7) SentimentView zusammenstellen und zurückgeben
        return SentimentView(
            coin=coin,
            score=score,
            regime=regime,
            news_surprise=news_surprise,
            veto=veto,
            reasoning=reasoning,
            sources=sources,
        )

    @staticmethod
    def _fallback(coin: str, fg_value: int, fg_classification: str) -> SentimentView:
        """Deterministischer Fallback wenn DB oder RAG-Corpus nicht verfügbar.

        news_surprise=None, veto=False (D-09). Score = reine F&G-Norm.
        """
        score: float = (fg_value - 50) / 50

        # Regime aus reinem F&G-Score (Grenzen inklusive)
        if score <= _FEAR_THRESHOLD:
            regime: Literal["FEAR", "NEUTRAL", "GREED"] = "FEAR"
        elif score >= _GREED_THRESHOLD:
            regime = "GREED"
        else:
            regime = "NEUTRAL"

        return SentimentView(
            coin=coin,
            score=score,
            regime=regime,
            news_surprise=None,
            veto=False,
            reasoning=(
                f"Fallback: Fear&Greed index {fg_value} ({fg_classification}). "
                "RAG-Corpus leer oder nicht verfügbar."
            ),
            sources=[],
        )
