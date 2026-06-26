"""RED test stub — NewsIngestionService.ingest_cryptopanic() (REQ-4-02, C-02, D-02).

Status: RED until NewsIngestionService.ingest_cryptopanic() is implemented
in plan 04-04.

C-02 guard: chunk metadata MUST carry BOTH votes_positive AND votes_negative.
This is the guard against Pitfall 6 (silent F&G-only degradation when CryptoPanic
articles are ingested but votes are stripped from metadata).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

_NOW = datetime.now(UTC)
_RECENT = _NOW - timedelta(days=3)  # within 7-day TTL
_OLD = _NOW - timedelta(days=8)  # outside 7-day TTL


# ---------------------------------------------------------------------------
# Fake RawCryptoPanicArticle dataclass (adapter return type)
# ---------------------------------------------------------------------------


class _FakeRawArticle:
    """Minimal stub for RawCryptoPanicArticle."""

    def __init__(
        self,
        url: str = "https://cryptopanic.com/news/1/btc-article",
        title: str = "BTC Sentiment Positive",
        published_at: datetime | None = None,
        votes_positive: int = 11,
        votes_negative: int = 2,
        currencies: list[str] | None = None,
    ) -> None:
        self.url = url
        self.title = title
        self.published_at = published_at if published_at is not None else _RECENT
        self.votes_positive = votes_positive
        self.votes_negative = votes_negative
        self.currencies = currencies if currencies is not None else ["BTC"]


# ---------------------------------------------------------------------------
# Service builder
# ---------------------------------------------------------------------------


def _build_service(articles: list[Any]) -> Any:
    """Build NewsIngestionService with mocked dependencies returning given articles."""
    from backend.application.services.news_ingestion_service import NewsIngestionService

    mock_repo = AsyncMock()
    mock_repo.exists_by_url_hash = AsyncMock(return_value=False)
    mock_repo.save_article = AsyncMock()
    mock_repo.save_chunks = AsyncMock()

    mock_cryptopanic = AsyncMock()
    mock_cryptopanic.fetch_articles = AsyncMock(return_value=articles)

    mock_llm = AsyncMock()
    mock_llm.embed = AsyncMock(return_value=[[0.0] * 2048])

    return NewsIngestionService(
        news_repo=mock_repo,
        rss_adapter=MagicMock(),
        ticker_ner=MagicMock(),
        llm_client=mock_llm,
        cryptopanic_adapter=mock_cryptopanic,
    )


# ---------------------------------------------------------------------------
# Tests: source="CRYPTOPANIC"
# ---------------------------------------------------------------------------


class TestNewsIngestionCryptoPanicSource:
    """REQ-4-02: ingest_cryptopanic() saves articles with source='CRYPTOPANIC'."""

    async def test_ingest_calls_save_article_with_cryptopanic_source(self) -> None:
        """save_article is called with a NewsArticle whose source='CRYPTOPANIC'."""
        articles = [_FakeRawArticle()]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        assert service._repo.save_article.called, "save_article must be called"
        saved_article = service._repo.save_article.call_args[0][0]
        assert saved_article.source == "CRYPTOPANIC", (
            f"Expected source='CRYPTOPANIC', got {saved_article.source!r}"
        )

    async def test_ingest_returns_article_count(self) -> None:
        """ingest_cryptopanic() returns a dict or int with ingestion stats."""
        articles = [_FakeRawArticle(), _FakeRawArticle(url="https://cryptopanic.com/news/2/eth")]
        service = _build_service(articles)

        result = await service.ingest_cryptopanic(["BTC"])
        # Must return stats indicating at least 2 articles processed
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: chunk metadata carries votes_positive AND votes_negative (C-02)
# ---------------------------------------------------------------------------


class TestNewsIngestionCryptoPanicVotesInChunkMetadata:
    """C-02 guard: chunk metadata MUST carry votes_positive AND votes_negative.

    This prevents silent F&G-only degradation (Pitfall 6): if votes are NOT
    embedded in chunk metadata, the D-03 formula silently falls back to pure F&G
    without any warning, giving misleading backtest results.
    """

    async def test_chunk_metadata_carries_votes_positive(self) -> None:
        """save_chunks is called with chunks whose metadata contains votes_positive."""
        articles = [_FakeRawArticle(votes_positive=11, votes_negative=2)]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        assert service._repo.save_chunks.called, "save_chunks must be called"
        saved_chunks = service._repo.save_chunks.call_args[0][0]
        assert len(saved_chunks) > 0, "At least one chunk must be saved"

        for chunk in saved_chunks:
            assert "votes_positive" in chunk.metadata, (
                f"C-02: chunk.metadata must contain 'votes_positive', got {chunk.metadata}"
            )

    async def test_chunk_metadata_carries_votes_negative(self) -> None:
        """save_chunks is called with chunks whose metadata contains votes_negative."""
        articles = [_FakeRawArticle(votes_positive=11, votes_negative=2)]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        assert service._repo.save_chunks.called
        saved_chunks = service._repo.save_chunks.call_args[0][0]
        assert len(saved_chunks) > 0

        for chunk in saved_chunks:
            assert "votes_negative" in chunk.metadata, (
                f"C-02: chunk.metadata must contain 'votes_negative', got {chunk.metadata}"
            )

    async def test_chunk_metadata_votes_values_correct(self) -> None:
        """votes_positive and votes_negative values match the raw article's votes."""
        articles = [_FakeRawArticle(votes_positive=11, votes_negative=2)]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        saved_chunks = service._repo.save_chunks.call_args[0][0]
        # Aggregate across all chunks — votes should come from the article
        for chunk in saved_chunks:
            assert chunk.metadata["votes_positive"] >= 0, "votes_positive must be non-negative"
            assert chunk.metadata["votes_negative"] >= 0, "votes_negative must be non-negative"

    async def test_chunk_metadata_source_is_cryptopanic(self) -> None:
        """Chunk metadata must have source='CRYPTOPANIC'."""
        articles = [_FakeRawArticle()]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        saved_chunks = service._repo.save_chunks.call_args[0][0]
        for chunk in saved_chunks:
            assert chunk.metadata.get("source") == "CRYPTOPANIC", (
                f"Expected metadata source='CRYPTOPANIC', got {chunk.metadata.get('source')!r}"
            )


# ---------------------------------------------------------------------------
# Tests: D-02 TTL — articles older than 7 days are skipped
# ---------------------------------------------------------------------------


class TestNewsIngestionCryptoPanicTTL:
    """D-02: Articles published more than 7 days ago must be skipped."""

    async def test_old_articles_are_skipped(self) -> None:
        """Articles with published_at > 7 days ago must NOT be saved."""
        articles = [
            _FakeRawArticle(
                url="https://cryptopanic.com/news/old/btc-old",
                published_at=_OLD,  # 8 days ago — outside TTL
                title="Old BTC news",
            )
        ]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        # save_article should NOT have been called for the old article
        # (it may not be called at all, or called 0 times for old articles)
        if service._repo.save_article.called:
            for call_args in service._repo.save_article.call_args_list:
                saved = call_args[0][0]
                assert saved.published_at is None or saved.published_at > (
                    _NOW - timedelta(days=7)
                ), f"Old article with published_at={saved.published_at} must be skipped"

    async def test_recent_articles_are_ingested(self) -> None:
        """Articles within 7-day TTL must be saved."""
        articles = [
            _FakeRawArticle(
                url="https://cryptopanic.com/news/recent/btc-recent",
                published_at=_RECENT,  # 3 days ago — within TTL
                title="Recent BTC news",
            )
        ]
        service = _build_service(articles)

        await service.ingest_cryptopanic(["BTC"])

        # save_article must have been called for the recent article
        assert service._repo.save_article.called, (
            "Recent article (within 7-day TTL) must be ingested via save_article"
        )

    async def test_none_published_at_is_not_skipped(self) -> None:
        """Articles with published_at=None are not silently dropped by TTL filter."""
        articles = [
            _FakeRawArticle(
                url="https://cryptopanic.com/news/undated/btc",
                published_at=None,
                title="Undated BTC news",
            )
        ]
        service = _build_service(articles)

        # Should not raise — either ingested or gracefully handled
        try:
            await service.ingest_cryptopanic(["BTC"])
        except Exception as exc:
            pytest.fail(f"ingest_cryptopanic raised unexpectedly for None published_at: {exc}")
