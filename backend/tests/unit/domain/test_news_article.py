"""Unit-Tests für NewsArticle-Entity."""

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from backend.domain.entities.news_article import NewsArticle

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 8, 7, 0, 0, tzinfo=UTC)


def _article(**kwargs: Any) -> NewsArticle:
    url = kwargs.get("url", "https://www.nzz.ch/finanzen/test-article-1")
    defaults = dict(
        id=uuid4(),
        url=url,
        url_hash=NewsArticle.hash_url(url),
        title="NESN steigt 2%",
        content="Nestlé verbucht Quartalsgewinn.",
        published_at=_NOW,
        source="NZZ",
        tickers=("NESN",),
        ingested_at=_NOW,
    )
    defaults.update(kwargs)
    return NewsArticle(**defaults)


class TestNewsArticle:
    def test_valid_nzz_article_creates_ok(self) -> None:
        a = _article()
        assert a.source == "NZZ"
        assert a.tickers == ("NESN",)

    def test_valid_srf_article_creates_ok(self) -> None:
        a = _article(source="SRF")
        assert a.source == "SRF"

    def test_invalid_source_raises(self) -> None:
        with pytest.raises(ValueError, match="source must be one of"):
            _article(source="REUTERS")

    def test_empty_url_raises(self) -> None:
        with pytest.raises(ValueError, match="url must be non-empty"):
            url = ""
            _article(url=url, url_hash=NewsArticle.hash_url("anything"))

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValueError, match="title must be non-empty"):
            _article(title="")

    def test_mismatched_url_hash_raises(self) -> None:
        with pytest.raises(ValueError, match="url_hash does not match"):
            _article(url_hash="bad_hash")

    def test_naive_ingested_at_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _article(ingested_at=datetime(2026, 6, 8, 7, 0, 0))

    def test_naive_published_at_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _article(published_at=datetime(2026, 6, 8, 7, 0, 0))

    def test_hash_url_is_sha256(self) -> None:
        url = "https://example.com/article"
        expected = hashlib.sha256(url.encode()).hexdigest()
        assert NewsArticle.hash_url(url) == expected

    def test_none_published_at_is_valid(self) -> None:
        a = _article(published_at=None)
        assert a.published_at is None
