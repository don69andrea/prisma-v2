"""Unit-Tests für NewsIngestionService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.services.news_ingestion_service import NewsIngestionService
from backend.infrastructure.adapters.rss_news_adapter import RawArticle
from backend.infrastructure.adapters.ticker_ner import SWISS_TICKERS, TickerNer

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 8, 7, 0, tzinfo=UTC)

_RAW_NESN = RawArticle(
    url="https://www.nzz.ch/finanzen/nesn-test",
    title="NESN legt zu",
    content="Nestlé verbucht Rekordumsatz im Q2.",
    published_at=_NOW,
    source="NZZ",
)

_RAW_EMPTY = RawArticle(
    url="https://www.srf.ch/news/bnf/no-ticker",
    title="Marktbericht",
    content="Allgemeiner Rückblick auf die Woche.",
    published_at=_NOW,
    source="SRF",
)


def _build_service(
    fetch_results: list[RawArticle] | None = None,
    already_exists: bool = False,
) -> tuple[NewsIngestionService, MagicMock, MagicMock]:
    mock_repo = AsyncMock()
    mock_repo.exists_by_url_hash.return_value = already_exists
    mock_repo.save_article = AsyncMock()
    mock_repo.save_chunks = AsyncMock()

    mock_rss = AsyncMock()
    mock_rss.fetch_articles.return_value = fetch_results or []

    mock_llm = AsyncMock()
    mock_llm.embed.return_value = [[0.1] * 2048]

    svc = NewsIngestionService(
        news_repo=mock_repo,
        rss_adapter=mock_rss,
        ticker_ner=TickerNer(SWISS_TICKERS),
        llm_client=mock_llm,
        feeds=[("NZZ", "https://www.nzz.ch/finanzen.rss")],
    )
    return svc, mock_repo, mock_llm


class TestNewsIngestionService:
    async def test_new_article_ingested(self) -> None:
        svc, mock_repo, _ = _build_service(fetch_results=[_RAW_NESN])
        stats = await svc.ingest_all()
        assert stats["ingested"] == 1
        assert stats["skipped_duplicate"] == 0
        mock_repo.save_article.assert_called_once()

    async def test_duplicate_article_skipped(self) -> None:
        svc, mock_repo, _ = _build_service(fetch_results=[_RAW_NESN], already_exists=True)
        stats = await svc.ingest_all()
        assert stats["ingested"] == 0
        assert stats["skipped_duplicate"] == 1
        mock_repo.save_article.assert_not_called()

    async def test_ticker_ner_detects_nesn(self) -> None:
        svc, mock_repo, _ = _build_service(fetch_results=[_RAW_NESN])
        await svc.ingest_all()
        saved_article = mock_repo.save_article.call_args[0][0]
        assert "NESN" in saved_article.tickers

    async def test_article_without_ticker_has_empty_tickers(self) -> None:
        svc, mock_repo, _ = _build_service(fetch_results=[_RAW_EMPTY])
        await svc.ingest_all()
        saved_article = mock_repo.save_article.call_args[0][0]
        assert saved_article.tickers == ()

    async def test_embedding_called_for_chunks(self) -> None:
        svc, _, mock_llm = _build_service(fetch_results=[_RAW_NESN])
        await svc.ingest_all()
        mock_llm.embed.assert_called_once()

    async def test_feed_fetch_error_counted(self) -> None:
        mock_repo = AsyncMock()
        mock_rss = AsyncMock()
        mock_rss.fetch_articles.side_effect = RuntimeError("network error")
        mock_llm = AsyncMock()

        svc = NewsIngestionService(
            news_repo=mock_repo,
            rss_adapter=mock_rss,
            ticker_ner=TickerNer(SWISS_TICKERS),
            llm_client=mock_llm,
            feeds=[("NZZ", "https://www.nzz.ch/finanzen.rss")],
        )
        stats = await svc.ingest_all()
        assert stats["errors"] == 1
        assert stats["ingested"] == 0

    async def test_no_articles_returns_zero_stats(self) -> None:
        svc, _, _ = _build_service(fetch_results=[])
        stats = await svc.ingest_all()
        assert stats == {"ingested": 0, "skipped_duplicate": 0, "errors": 0}
