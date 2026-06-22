"""RED test stub — NewsArticle entity with CRYPTOPANIC source (REQ-4-03).

These tests verify that NewsArticle accepts source="CRYPTOPANIC" and continues to
accept NZZ/SRF while rejecting unknown sources.

Status: RED until backend/domain/entities/news_article.py adds "CRYPTOPANIC"
to _VALID_SOURCES (plan 04-01).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC)


def _article(**kwargs: Any) -> Any:
    from backend.domain.entities.news_article import NewsArticle

    url = kwargs.get("url", "https://cryptopanic.com/news/123/btc-hits-ath")
    defaults = dict(
        id=uuid4(),
        url=url,
        url_hash=NewsArticle.hash_url(url),
        title="BTC hits ATH",
        content="Bitcoin reaches new all-time high.",
        published_at=_NOW,
        source="CRYPTOPANIC",
        tickers=("BTC",),
        ingested_at=_NOW,
    )
    defaults.update(kwargs)
    return NewsArticle(**defaults)


class TestNewsArticleCryptoPanicSource:
    """REQ-4-03: NewsArticle must accept source='CRYPTOPANIC'."""

    def test_cryptopanic_source_accepted(self) -> None:
        """NewsArticle with source='CRYPTOPANIC' creates without error."""
        a = _article(source="CRYPTOPANIC")
        assert a.source == "CRYPTOPANIC"

    def test_nzz_source_still_accepted(self) -> None:
        """Existing NZZ source remains valid after adding CRYPTOPANIC."""
        url = "https://www.nzz.ch/test-article"
        from backend.domain.entities.news_article import NewsArticle

        a = _article(
            url=url,
            url_hash=NewsArticle.hash_url(url),
            source="NZZ",
            tickers=("NESN",),
        )
        assert a.source == "NZZ"

    def test_srf_source_still_accepted(self) -> None:
        """Existing SRF source remains valid after adding CRYPTOPANIC."""
        url = "https://www.srf.ch/news/test-article"
        from backend.domain.entities.news_article import NewsArticle

        a = _article(
            url=url,
            url_hash=NewsArticle.hash_url(url),
            source="SRF",
            tickers=("NESN",),
        )
        assert a.source == "SRF"

    def test_unknown_source_still_rejected(self) -> None:
        """An unrecognised source like 'UNKNOWN' must still raise ValueError."""
        with pytest.raises(ValueError, match="source must be one of"):
            _article(source="UNKNOWN")

    def test_reuters_source_rejected(self) -> None:
        """REUTERS is not in _VALID_SOURCES — must raise ValueError."""
        with pytest.raises(ValueError, match="source must be one of"):
            _article(source="REUTERS")

    def test_cryptopanic_with_votes_metadata(self) -> None:
        """CRYPTOPANIC articles carry tickers from CryptoPanic currencies tags."""
        a = _article(source="CRYPTOPANIC", tickers=("BTC", "ETH"))
        assert "BTC" in a.tickers
        assert "ETH" in a.tickers
